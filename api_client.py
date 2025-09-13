import functools
import itertools
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

import requests
from binance.exceptions import BinanceAPIException as ClientError
from binance.spot import Spot as SpotClient
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient


# Stubs para Config e Security para garantir a validade sintática
class Config:
    def __init__(self):
        self.api_key = os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_API_SECRET", "")
        self.base_urls = {
            "main": "https://api.binance.com",
            "alternatives": [
                "https://api1.binance.com",
                "https://api2.binance.com",
                "https://api3.binance.com",
            ],
        }


class Security:
    def __init__(self, secret):
        pass


REQUEST_WEIGHT_LIMIT_PER_MINUTE = 6000


def _handle_request_errors(weight: int = 1) -> Callable:
    """Decorador para tratar erros de requisição da API, implementar failover,
    gerenciamento de limite de taxa e retentativas.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self: "ApiClient", *args, **kwargs) -> Any:
            try:
                with self.rate_limit_lock:
                    if time.time() - self.last_weight_reset_time > 60:
                        self.rate_limit_weight = 0
                        self.last_weight_reset_time = time.time()
                    if (
                        self.rate_limit_weight + weight
                        > REQUEST_WEIGHT_LIMIT_PER_MINUTE
                    ):
                        wait_time = 60 - (time.time() - self.last_weight_reset_time)
                        if wait_time > 0:
                            logging.warning(
                                f"Rate limit approaching. Waiting for {wait_time:.2f}s...",
                            )
                            time.sleep(wait_time)
                        self.rate_limit_weight = 0
                        self.last_weight_reset_time = time.time()

                response = func(self, *args, **kwargs)
                if isinstance(response, tuple) and len(response) == 2:
                    data, weight_info = response
                    with self.rate_limit_lock:
                        self.rate_limit_weight = int(
                            weight_info.get("x-mbx-used-weight-1m", 0),
                        )
                    return data
                else:
                    return response
            except ClientError as e:
                if e.status_code in [429, 418]:
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    logging.warning(
                        f"Rate limit error ({e.status_code}). "
                        f"Waiting for {retry_after} seconds.",
                    )
                    time.sleep(retry_after)
                else:
                    logging.warning(
                        f"Client error ({e.status_code}) for {func.__name__}: {e.error_message}. "
                        f"Attempting failover.",
                    )
                    self._perform_failover()
                return wrapper(self, *args, **kwargs)
            except requests.RequestException as e:
                logging.warning(
                    f"Connection failed for {func.__name__}: {e}. Attempting failover.",
                )
                self._perform_failover()
                return wrapper(self, *args, **kwargs)

        return wrapper

    return decorator


class ApiClient:
    """Cliente para interagir com a API da Binance, com failover e rate limiting."""

    def __init__(self, config: Config):
        self.config = config
        self.security = Security(self.config.api_secret)
        self.endpoints: list[str] = []
        self.endpoint_cycle: itertools.cycle[str] | None = None
        self.spot_client: SpotClient = None
        self._select_best_endpoint_and_init_client()

        self._stop_event = None

        self.rate_limit_weight = 0
        self.last_weight_reset_time = time.time()
        self.rate_limit_lock = threading.Lock()

        self.market_websocket_client: SpotWebsocketStreamClient | None = None
        self.market_websocket_running = False
        self._market_ws_callback: Callable[[dict], None] | None = None

        self.user_websocket_client: SpotWebsocketStreamClient | None = None
        self.user_websocket_running = False
        self._user_ws_callback: Callable[[dict], None] | None = None

        self.depth_websocket_clients: dict[str, SpotWebsocketStreamClient] = {}
        self.depth_websocket_running: dict[str, bool] = {}

        self.time_offset_ms: int = 0
        self._sync_server_time()

    def _create_spot_client(self, base_url: str) -> SpotClient:
        return SpotClient(
            base_url=base_url,
            api_key=self.config.api_key,
            api_secret=self.config.api_secret,
            show_limit_usage=True,
        )

    def _select_best_endpoint_and_init_client(self) -> None:
        all_urls = [self.config.base_urls["main"]] + self.config.base_urls[
            "alternatives"
        ]
        latencies = {url: self._get_endpoint_latency(url) for url in all_urls}
        sorted_endpoints = sorted(latencies.items(), key=lambda item: item[1])
        self.endpoints = [url for url, lat in sorted_endpoints if lat != float("inf")]
        if not self.endpoints:
            raise RuntimeError("Nenhum endpoint da API da Binance está acessível.")
        best_endpoint = self.endpoints[0]
        self.endpoint_cycle = itertools.cycle(self.endpoints)
        logging.info(f"Endpoints ordenados por latência: {self.endpoints}")
        logging.info(f"Selecionado o melhor endpoint: {best_endpoint}")
        self.spot_client = self._create_spot_client(best_endpoint)

    def _get_endpoint_latency(self, url: str) -> float:
        try:
            temp_client = self._create_spot_client(url)
            start_time = time.time()
            temp_client.ping()
            return time.time() - start_time
        except (requests.RequestException, ClientError):
            logging.warning(f"Endpoint {url} falhou no teste de ping.")
            return float("inf")

    def _perform_failover(self) -> None:
        if not self.endpoint_cycle:
            raise RuntimeError("Ciclo de endpoints não inicializado.")
        next_endpoint = next(self.endpoint_cycle)
        logging.info(f"Realizando failover para o endpoint: {next_endpoint}")
        self.spot_client = self._create_spot_client(next_endpoint)
        self._sync_server_time()

    def _current_timestamp(self) -> int:
        return int(time.time() * 1000) + self.time_offset_ms

    @_handle_request_errors(weight=1)
    def _sync_server_time(self) -> None:
        try:
            server_time = self.spot_client.time()["serverTime"]
            local_time = int(time.time() * 1000)
            self.time_offset_ms = server_time - local_time
            logging.info(f"Time offset adjusted to {self.time_offset_ms} ms")
        except (KeyError, TypeError):
            logging.warning("Não foi possível sincronizar o tempo do servidor")
            self.time_offset_ms = 0

    # --- Métodos da API REST ---
    @_handle_request_errors(weight=20)
    def get_exchange_info(self) -> dict:
        return self.spot_client.exchange_info()

    @_handle_request_errors(weight=20)
    def get_account_info(self) -> dict:
        return self.spot_client.account()

    @_handle_request_errors(weight=1)
    def place_order(self, order_params: dict) -> dict:
        if "timestamp" not in order_params:
            order_params["timestamp"] = self._current_timestamp()
        return self.spot_client.new_order(**order_params)

    @_handle_request_errors(weight=1)
    def test_place_order(self, order_params: dict) -> dict:
        """Envia uma ordem de teste para validação sem execução."""
        if "timestamp" not in order_params:
            order_params["timestamp"] = self._current_timestamp()
        return self.spot_client.new_order_test(**order_params)

    @_handle_request_errors(weight=1)
    def get_system_status(self) -> dict:
        """Verifica o status do sistema da Binance."""
        return self.spot_client.system_status()

    @_handle_request_errors(weight=10)
    def get_trading_fees(self) -> dict:
        """Obtém as taxas de negociação para a conta."""
        return self.spot_client.trade_fee()

    

    def get_exchange_limits(self) -> dict:
        """Extrai limites relevantes do exchange_info para satisfazer o DataAnalyzer."""
        exchange_info = self.get_exchange_info()
        symbols_limits = {}
        for s in exchange_info.get("symbols", []):
            filters = {f["filterType"]: f for f in s.get("filters", [])}
            symbols_limits[s["symbol"]] = {
                "min_qty": filters.get("LOT_SIZE", {}).get("minQty"),
                "max_qty": filters.get("LOT_SIZE", {}).get("maxQty"),
                "step_size": filters.get("LOT_SIZE", {}).get("stepSize"),
                "min_notional": filters.get("MIN_NOTIONAL", {}).get("minNotional"),
            }
        return {"symbols": symbols_limits, "min_notional": 10.0}

    

    @_handle_request_errors(weight=2)
    def get_order(self, symbol: str, order_id: str) -> dict:
        """Obtém detalhes de uma ordem específica."""
        return self.spot_client.get_order(symbol, orderId=order_id)

    @_handle_request_errors(weight=1)
    def get_ticker_price(self, symbol: str) -> dict:
        """Obtém o preço de ticker para um símbolo."""
        return self.spot_client.ticker_price(symbol)

    @_handle_request_errors(weight=10)
    def get_my_trades(self, symbol: str, limit: int = 1000) -> list:
        """Obtém os trades executados para um símbolo."""
        return self.spot_client.my_trades(symbol, limit=limit)

    @_handle_request_errors(weight=2)
    def get_open_orders(self, symbol: str = None) -> list:
        """Obtém todas as ordens abertas."""
        if symbol:
            return self.spot_client.get_open_orders(symbol=symbol)
        return self.spot_client.get_open_orders()

    @_handle_request_errors(weight=1)
    def cancel_order(self, symbol: str, order_id: str) -> dict:
        """Cancela uma ordem aberta."""
        return self.spot_client.cancel_order(symbol, orderId=order_id)

    # --- WebSockets ---
    def start_market_data_websocket(self, callback: Callable[[dict], None]):
        if self.market_websocket_running:
            logging.warning("Market Data WebSocket já está em execução.")
            return
        logging.info("Iniciando Market Data WebSocket...")
        self.market_websocket_client = SpotWebsocketStreamClient(
            on_message=callback,
            on_close=lambda ws: self._handle_market_ws_close(ws),
        )
        self._market_ws_callback = callback
        self.market_websocket_running = True
        self.market_websocket_client.subscribe(stream="!ticker@arr")

    def set_stop_event(self, stop_event: threading.Event):
        self._stop_event = stop_event

    def _handle_market_ws_close(self, ws):
        self.market_websocket_running = False
        # SÓ RECONECTA SE O BOT NÃO ESTIVER PARANDO
        if self._stop_event and self._stop_event.is_set():
            logging.info("Market Data WebSocket fechado durante o desligamento do bot.")
            return

        logging.info("Market Data WebSocket fechado. Tentando reconectar...")
        time.sleep(5)
        if self._market_ws_callback:
            self.start_market_data_websocket(self._market_ws_callback)

    def start_user_data_websocket(self, callback: Callable[[dict], None]):
        if self.user_websocket_running:
            logging.warning("User Data WebSocket já está em execução.")
            return
        logging.info("Iniciando User Data WebSocket (método moderno)...")
        try:
            self.user_websocket_client = SpotWebsocketStreamClient(
                on_message=callback,
                on_close=lambda ws: self._handle_user_ws_close(ws),
                api_key=self.config.api_key,
                api_secret=self.config.api_secret,
            )
            self._user_ws_callback = callback
            self.user_websocket_running = True
            self.user_websocket_client.user_data()
        except Exception as e:
            logging.exception(f"Erro ao iniciar User Data WebSocket: {e}")
            self.user_websocket_running = False

    def _handle_user_ws_close(self, ws):
        self.user_websocket_running = False
        logging.info("User Data WebSocket fechado. Tentando reconectar...")
        time.sleep(5)
        if self._user_ws_callback:
            self.start_user_data_websocket(self._user_ws_callback)

    def start_depth_websocket(self, symbol: str, callback: Callable[[dict], None]):
        """Inicia um WebSocket de profundidade para um símbolo específico."""
        if symbol in self.depth_websocket_clients:
            logging.warning(f"Depth WebSocket para {symbol} já está em execução.")
            return
        logging.info(f"Iniciando Depth WebSocket para {symbol}...")

        def on_close_callback(ws):
            logging.warning(
                f"Depth WebSocket para {symbol} fechado. Removendo da lista de ativos."
            )
            if symbol in self.depth_websocket_running:
                self.depth_websocket_running[symbol] = False
            if symbol in self.depth_websocket_clients:
                del self.depth_websocket_clients[symbol]

        client = SpotWebsocketStreamClient(
            on_message=callback, on_close=on_close_callback
        )
        client.partial_book_depth(symbol=symbol, level=5, speed=1000)
        self.depth_websocket_clients[symbol] = client
        self.depth_websocket_running[symbol] = True

    def stop_depth_websocket(self, symbol: str):
        """Para um WebSocket de profundidade para um símbolo específico."""
        if symbol in self.depth_websocket_clients:
            logging.info(f"Parando Depth WebSocket para {symbol}...")
            self.depth_websocket_clients[symbol].stop()
            del self.depth_websocket_clients[symbol]
            if symbol in self.depth_websocket_running:
                del self.depth_websocket_running[symbol]

    def is_websocket_running(self) -> bool:
        """Verifica se o websocket principal de mercado está ativo."""
        return self.market_websocket_running

    def stop_websockets(self):
        logging.info("Parando todos os WebSockets...")
        if self.market_websocket_client:
            self.market_websocket_client.stop()
            self.market_websocket_running = False
        if self.user_websocket_client:
            self.user_websocket_client.stop()
            self.user_websocket_running = False
        self.stop_all_depth_websockets()

    def stop_all_depth_websockets(self):
        for symbol in list(self.depth_websocket_clients.keys()):
            if self.depth_websocket_clients[symbol]:
                self.depth_websocket_clients[symbol].stop()
        self.depth_websocket_clients.clear()
        self.depth_websocket_running.clear()
