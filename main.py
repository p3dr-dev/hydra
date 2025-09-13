"""Módulo principal para o Bot de Trading Autônomo, agora orientado a eventos via WebSockets."""

import logging
import threading
import time
from collections import deque
from decimal import Decimal

# Garantir que os módulos locais sejam encontrados
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from src.hydra.api_client import ApiClient
from src.hydra.config import Config, ConfigError
from src.hydra.dashboard import create_dashboard, TradingMetrics
from src.hydra.data_analyzer import DataAnalyzer
from src.hydra.order_executor import OrderExecutor
from src.hydra.performance_monitor import PerformanceMonitor
from src.hydra.risk_manager import RiskManager

# Configuração do logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class TradingBot:
    """O robô de trading que orquestra a análise e execução de forma reativa."""

    def __init__(self, config: Config):
        self.api_client = ApiClient(config)
        self.risk_manager = RiskManager(self.api_client, None)  # O DataAnalyzer será injetado depois
        self.data_analyzer = DataAnalyzer(self.api_client, self.risk_manager)
        self.risk_manager.data_analyzer = self.data_analyzer # Injeta o data_analyzer no risk_manager
        self.order_executor = OrderExecutor(
            self.api_client,
            self.data_analyzer,
            self.risk_manager,
        )
        self._stop_event = threading.Event()
        self.api_client.set_stop_event(self._stop_event) # Adicione esta linha
        self.tickers = {}
        self.running = False
        self._lock = threading.Lock()
        self.order_books = {}
        self.active_depth_subscriptions = set()
        self.performance_monitor = PerformanceMonitor()
        self.dashboard = create_dashboard(enable_web=True, port=5000)
        self.trading_stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit": Decimal(0),
            "total_volume": Decimal(0),
            "trade_times": deque(maxlen=100),
        }
        self._graph_rebuild_counter = 0

    def _on_ticker_message(self, ws_client, message):
        try:
            import json
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except json.JSONDecodeError:
                    logging.exception(f"❌ Falha ao fazer parse da mensagem string: {message}")
                    return

            if isinstance(message, dict) and "result" in message:
                logging.info(f"✅ Subscrito ao stream com sucesso: {message}")
                return

            if isinstance(message, list):
                with self._lock:
                    for ticker in message:
                        if "s" in ticker and "b" in ticker and "a" in ticker:
                            self.tickers[ticker["s"]] = {
                                "bidPrice": ticker["b"],
                                "askPrice": ticker["a"],
                                "quoteVolume": ticker.get("Q", "0"),
                            }
            elif isinstance(message, dict) and "s" in message and "b" in message and "a" in message:
                with self._lock:
                    self.tickers[message["s"]] = {
                        "bidPrice": message["b"],
                        "askPrice": message["a"],
                        "quoteVolume": message.get("Q", "0"),
                    }
            else:
                logging.warning(f"⚠️ Mensagem de ticker não reconhecida: {type(message)} - {message}")
                return

            if self.tickers:
                if not hasattr(self, "_analysis_counter"):
                    self._analysis_counter = 0
                self._analysis_counter += 1

                if self._analysis_counter % 10 == 0:
                    with self._lock:
                        current_tickers = self.tickers.copy()
                        current_order_books = self.order_books.copy()
                    
                    logging.info(f"🚀 Iniciando ciclo de análise com {len(current_tickers)} tickers")
                    self.run_cycle(current_tickers, current_order_books)

        except Exception as e:
            logging.error(f"❌ Erro ao processar mensagem do ticker: {e}", exc_info=True)

    def _on_depth_message(self, ws_client, message):
        try:
            import json
            if isinstance(message, str):
                message = json.loads(message)
            if message.get("e") == "depthUpdate" and "s" in message:
                symbol = message["s"]
                with self._lock:
                    self.order_books[symbol] = {
                        "bids": message.get("b", []),
                        "asks": message.get("a", []),
                    }
        except Exception as e:
            logging.error(f"❌ Erro ao processar mensagem de profundidade: {e}", exc_info=True)

    def run_cycle(self, current_tickers: dict, current_order_books: dict):
        logging.info("🔄 INICIANDO CICLO DE ANÁLISE")
        system_status = self.api_client.get_system_status()
        if system_status.get("status") != 0:
            logging.warning(f"⚠️ Ciclo de análise pausado: {system_status.get('msg')}")
            return

        if not current_tickers:
            logging.warning("⚠️ Nenhum ticker disponível para o ciclo de análise")
            return

        total_volume_24h = Decimal(0)
        spreads = []
        for ticker_data in current_tickers.values():
            total_volume_24h += Decimal(ticker_data.get("quoteVolume", "0"))
            try:
                bid = Decimal(ticker_data.get("bidPrice", "0"))
                ask = Decimal(ticker_data.get("askPrice", "0"))
                if bid > 0:
                    spreads.append((ask - bid) / bid)
            except Exception:
                continue
        avg_spread_pct = (sum(spreads) / len(spreads)) if spreads else Decimal(0)

        market_metrics = {"avg_spread_pct": float(avg_spread_pct), "total_volume_24h": float(total_volume_24h)}
        strategy_params = self.risk_manager.get_dynamic_strategy_parameters(market_metrics)

        # Prioritiza a análise para os ativos de maior volume
        top_symbols = sorted(
            current_tickers.items(),
            key=lambda item: float(item[1].get("quoteVolume", "0")),
            reverse=True,
        )[:20]

        major_assets = set()
        for symbol, _ in top_symbols:
            if symbol in self.data_analyzer.symbol_to_assets_map:
                assets = self.data_analyzer.symbol_to_assets_map[symbol]
                major_assets.add(assets["base"])
                major_assets.add(assets["quote"])

        try:
            account_balance = self.order_executor.get_account_balance()
            if not account_balance:
                return
            
            all_available_assets = [a for a, b in account_balance.items() if b["free"] > 0 and a in self.data_analyzer.all_assets]
            
            # Filtra os ativos disponíveis para incluir apenas os de maior volume
            available_assets = [asset for asset in all_available_assets if asset in major_assets]
            if not available_assets:
                # Fallback para todos os ativos se nenhum dos principais estiver disponível
                available_assets = all_available_assets

            if not available_assets:
                return
        except Exception as e:
            logging.error(f"❌ Erro ao obter portfólio da conta: {e}", exc_info=True)
            return

        all_profitable_paths = []
        for start_asset in available_assets:
            start_amount = float(account_balance[start_asset]["free"])
            try:
                profitable_paths = self.data_analyzer.find_profitable_paths(
                    tickers=current_tickers,
                    order_books=current_order_books,
                    start_asset=start_asset,
                    start_amount=start_amount,
                    strategy_params=strategy_params
                )
                if profitable_paths:
                    all_profitable_paths.extend(profitable_paths)
            except Exception as e:
                logging.exception(f"❌ Erro ao analisar {start_asset}: {e}")

        if not all_profitable_paths:
            logging.info("ℹ️ Nenhuma oportunidade de arbitragem lucrativa encontrada.")
            return

        required_symbols = {s for p_info in all_profitable_paths for s in self.data_analyzer.get_path_symbols(p_info["path"], current_tickers)}
        new_subscriptions = required_symbols - self.active_depth_subscriptions
        for symbol in new_subscriptions:
            self.api_client.start_depth_websocket(symbol, self._on_depth_message)
            self.active_depth_subscriptions.add(symbol)

        unused_subscriptions = self.active_depth_subscriptions - required_symbols
        for symbol in unused_subscriptions:
            self.api_client.stop_depth_websocket(symbol)
            self.active_depth_subscriptions.remove(symbol)

        if new_subscriptions:
            time.sleep(2)

        dynamic_params = self.risk_manager.get_dynamic_risk_parameters()
        risk_percentage = dynamic_params.get("max_portfolio_risk", 0.01)
        trade_instructions = self.risk_manager.generate_trade_instructions(
            profitable_paths=all_profitable_paths,
            risk_percentage=risk_percentage,
            tickers=current_tickers,
            order_books=current_order_books,
        )

        if not trade_instructions:
            return

        execution_results = self.order_executor.execute_instructions(
            trade_instructions,
            current_tickers,
            current_order_books,
        )

        if execution_results:
            successful_trades = [r for r in execution_results if r.success]
            failed_trades = [r for r in execution_results if not r.success]

            for result in successful_trades:
                self.trading_stats["total_trades"] += 1
                self.trading_stats["successful_trades"] += 1
                self.trading_stats["total_profit"] += result.profit_loss
                self.trading_stats["total_volume"] += result.initial_amount
                self.trading_stats["trade_times"].append(result.execution_time)

            for _ in failed_trades:
                self.trading_stats["total_trades"] += 1
                self.trading_stats["failed_trades"] += 1

            if self.dashboard:
                success_rate = (self.trading_stats["successful_trades"] / max(1, self.trading_stats["total_trades"])) * 100
                avg_profit = self.trading_stats["total_profit"] / max(1, self.trading_stats["successful_trades"])
                active_tickers_count = len(current_tickers)

                new_metrics = TradingMetrics(
                    total_trades=self.trading_stats["total_trades"],
                    successful_trades=self.trading_stats["successful_trades"],
                    failed_trades=self.trading_stats["failed_trades"],
                    total_profit=float(self.trading_stats["total_profit"]),
                    success_rate=success_rate,
                    avg_profit=float(avg_profit),
                    active_tickers=active_tickers_count,
                    market_volatility=float(avg_spread_pct * 100),
                    market_volume=float(total_volume_24h),
                )
                self.dashboard.update_metrics(new_metrics)

    def start(self):
        self.running = True
        logging.info("Iniciando o bot de trading...")
        try:
            self.performance_monitor.start()
            if self.dashboard:
                self.dashboard.start()
            self.data_analyzer.build_trading_graph()
            self.api_client.start_market_data_websocket(self._on_ticker_message)
            logging.info("Bot em execução, aguardando dados do mercado...")
            timeout_counter = 0
            while not self._stop_event.is_set():
                time.sleep(1)
                timeout_counter += 1
                self._graph_rebuild_counter += 1
                if self._graph_rebuild_counter >= 21600:
                    logging.info("Reconstruindo o grafo de negociação periodicamente...")
                    self.data_analyzer.build_trading_graph()
                    self._graph_rebuild_counter = 0
                if timeout_counter % 30 == 0:
                    logging.info("Bot ainda em execução, aguardando dados do mercado...")
        except Exception as e:
            logging.exception(f"Erro durante a execução do bot: {e}")
            self.running = False
            raise

    def stop(self):
        if self.running:
            self.running = False
            self.api_client.stop_websockets()
            self._stop_event.set()
            logging.info("Parando o bot de trading...")

def main():
    bot = None
    try:
        logging.info("Iniciando o Bot de Trading...")
        logging.warning("🚨 O BOT ESTÁ EM MODO DE PRODUÇÃO!")
        config = Config.from_env()
        bot = TradingBot(config=config)
        bot.start()
    except ConfigError as e:
        logging.exception(f"Erro de configuração: {e}")
    except KeyboardInterrupt:
        logging.info("Interrupção do usuário recebida.")
    finally:
        if bot:
            bot.stop()
        logging.info("Bot finalizado.")

if __name__ == "__main__":
    main()