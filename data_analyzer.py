"""Módulo para análise de dados da exchange e identificação de oportunidades de trading.
Implementa uma abordagem de grafo para encontrar os caminhos de negociação mais lucrativos.
"""

import logging
import time
from typing import Any
from collections import deque

from api_client import ApiClient


class DataAnalyzer:
    """Analisa dados de mercado em tempo real para encontrar oportunidades de trading."""

    def __init__(self, api_client: ApiClient, risk_manager: "RiskManager"):
        """Inicializa o analisador de dados.

        Args:
            api_client (ApiClient): Cliente da API para buscar dados.
            risk_manager (RiskManager): Gerenciador de risco para obter parâmetros de estratégia.

        """
        self.api_client = api_client
        self.risk_manager = risk_manager
        self.trading_graph: dict[str, list[str]] = {}
        self.all_assets: set[str] = set()
        self.symbol_to_assets_map: dict[str, dict[str, str]] = {}

        # Parâmetros dinâmicos - serão obtidos da API
        self.trading_parameters = None
        self.min_profit_threshold = 0.0001  # Temporário, será substituído
        self.min_liquidity_threshold = 100  # Temporário, será substituído
        self.max_spread_threshold = 0.01  # Temporário, será substituído
        self.max_path_length = 2  # Temporário, será substituído
        self.max_paths = 100000  # Limite de caminhos a serem explorados
        self.min_notional = 10  # Temporário, será substituído
        self.taker_commission = 0.001  # Temporário, será substituído
        self.maker_commission = 0.0001  # Temporário, será substituído

        

    def get_commission_for_symbol(self, symbol: str, is_maker: bool = False) -> float:
        """Obtém a comissão específica para um símbolo da API da Binance.

        Args:
            symbol (str): O símbolo do par de trading.
            is_maker (bool): Se True, retorna comissão maker, senão taker.

        Returns:
            float: A comissão para o símbolo.

        """
        try:
            if self.trading_parameters:
                fees = self.api_client.get_trading_fees()
                symbol_fees = fees.get("symbols", {}).get(symbol, {})

                if is_maker:
                    return symbol_fees.get("maker", self.maker_commission)
                return symbol_fees.get("taker", self.taker_commission)
            return self.maker_commission if is_maker else self.taker_commission

        except Exception as e:
            logging.exception(f"Erro ao obter comissão para {symbol}: {e}")
            return self.maker_commission if is_maker else self.taker_commission

    def get_symbol_limits(self, symbol: str) -> dict[str, float]:
        """Obtém os limites específicos para um símbolo da API da Binance.

        Args:
            symbol (str): O símbolo do par de trading.

        Returns:
            dict: Limites do símbolo com estrutura:
            {
                'min_qty': 0.00001,
                'max_qty': 1000,
                'step_size': 0.00001,
                'min_notional': 10.0,
                'max_notional': 9000000.0
            }

        """
        try:
            limits = self.api_client.get_exchange_limits()
            if limits:
                return limits.get("symbols", {}).get(symbol, {})
            return {}

        except Exception as e:
            logging.exception(f"Erro ao obter limites para {symbol}: {e}")
            return {}

    def get_market_quality_for_symbol(self, symbol: str) -> dict[str, float]:
        """Obtém métricas de qualidade do mercado para um símbolo específico.

        Args:
            symbol (str): O símbolo do par de trading.

        Returns:
            dict: Métricas de qualidade com estrutura:
            {
                'avg_spread': 0.0005,
                'avg_volume': 50000000,
                'volatility': 0.03,
                'liquidity_score': 0.95
            }

        """
        try:
            metrics = self.api_client.get_market_quality_metrics()
            if metrics:
                return metrics.get("symbols", {}).get(symbol, {})
            return {}

        except Exception as e:
            logging.exception(f"Erro ao obter métricas de qualidade para {symbol}: {e}")
            return {}

    def build_trading_graph(self) -> None:
        """Constrói um grafo de todos os pares de negociação a partir do exchange_info."""
        logging.info("Construindo o grafo de negociação...")
        
        # --- INÍCIO DA MELHORIA ---
        max_retries = 3
        for attempt in range(max_retries):
            exchange_info = self.api_client.get_exchange_info()
            if isinstance(exchange_info, dict) and "symbols" in exchange_info:
                break # Sucesso, sai do loop
            
            logging.warning(f"Tentativa {attempt + 1}/{max_retries} de construir o grafo falhou. Tentando novamente em 10 segundos...")
            time.sleep(10)
        else: # Este 'else' pertence ao 'for'. É executado se o loop terminar sem 'break'.
            logging.error(
                "NÃO FOI POSSÍVEL OBTER INFORMAÇÕES DA EXCHANGE APÓS MÚLTIPLAS TENTATIVAS. O BOT PODE NÃO FUNCIONAR CORRETAMENTE.",
            )
            return
        # --- FIM DA MELHORIA ---

        self.trading_graph.clear()
        self.all_assets.clear()
        self.symbol_to_assets_map.clear()

        for symbol_info in exchange_info["symbols"]:
            if (
                symbol_info.get("status") == "TRADING"
                and "baseAsset" in symbol_info
                and "quoteAsset" in symbol_info
            ):
                base = symbol_info["baseAsset"]
                quote = symbol_info["quoteAsset"]
                symbol = symbol_info["symbol"]
                self.symbol_to_assets_map[symbol] = {"base": base, "quote": quote}

                self.all_assets.add(base)
                self.all_assets.add(quote)

                if base not in self.trading_graph:
                    self.trading_graph[base] = []
                if quote not in self.trading_graph:
                    self.trading_graph[quote] = []

                self.trading_graph[base].append(quote)
                self.trading_graph[quote].append(base)
        logging.info(
            f"Grafo de negociação construído com {len(self.all_assets)} ativos e {len(self.trading_graph)} nós.",
        )

    def find_profitable_paths(
        self,
        tickers: dict,
        order_books: dict,
        start_asset: str,
        start_amount: float,
        strategy_params: dict, # Adicionado
    ) -> list[dict]:
        """Encontra caminhos lucrativos a partir de um ativo inicial."""
        if not tickers or not start_asset or start_amount <= 0:
            return []

        # Usa os parâmetros recebidos em vez dos atributos da classe
        max_depth = strategy_params.get("max_path_length", 2)
        min_profit_threshold = strategy_params.get("min_profit_threshold", 0.001)

        # Garante que o grafo esteja construído
        if not self.trading_graph or not self.all_assets:
            self.build_trading_graph()

        if start_asset not in self.all_assets:
            return []

        if start_amount < self.min_notional:
            return []

        profitable_paths = []
        queue = deque([(start_asset, [start_asset], start_amount, 0)])
        visited = set()

        while queue and len(profitable_paths) < self.max_paths:
            current_asset, path, current_amount, depth = queue.popleft()

            if depth >= max_depth:
                continue

            state = (current_asset, depth)
            if state in visited:
                continue
            visited.add(state)

            neighbors = self.trading_graph.get(current_asset, [])
            for neighbor in neighbors:
                if neighbor == current_asset:
                    continue

                symbol, _side = DataAnalyzer.get_symbol_and_side(
                    tickers,
                    current_asset,
                    neighbor,
                )
                if not symbol:
                    continue

                new_amount = self.calculate_trade(
                    tickers,
                    order_books,
                    current_asset,
                    neighbor,
                    float(current_amount),
                )
                if new_amount <= 0:
                    continue

                new_path = path + [neighbor]

                if len(new_path) >= 2:
                    profit = self.calculate_path_profit(
                        tickers,
                        order_books,
                        new_path,
                        float(start_amount),
                    )
                    if profit:
                        profit_pct = profit.get("profit_percent", 0)
                        if profit_pct > min_profit_threshold:
                            profitable_paths.append(profit)

                if depth < max_depth - 1:
                    queue.append((neighbor, new_path, new_amount, depth + 1))

        profitable_paths.sort(key=lambda x: x["profit_percent"], reverse=True)
        return profitable_paths

    def _check_path_liquidity(
        self,
        tickers: dict[str, dict[str, str]],
        path: list[str],
    ) -> bool:
        """Verifica se um caminho tem liquidez suficiente para execução.

        Args:
            tickers (dict): Dicionário de tickers
            path (list): Lista de ativos no caminho

        Returns:
            bool: True se tem liquidez suficiente

        """
        for i in range(len(path) - 1):
            asset_from = path[i]
            asset_to = path[i + 1]

            # Suporta símbolos com e sem underscore: ex. BTCUSDT e BTC_USDT
            candidate_symbols = [
                f"{asset_from}{asset_to}",
                f"{asset_to}{asset_from}",
                f"{asset_from}_{asset_to}",
                f"{asset_to}_{asset_from}",
            ]

            found_any = False
            for symbol in candidate_symbols:
                if symbol in tickers:
                    found_any = True
                    ticker_data = tickers[symbol]
                    # Se não existir informação de volume, não bloqueia o caminho
                    if "Q" in ticker_data:
                        try:
                            volume = float(ticker_data["Q"])
                            if volume < self.min_liquidity_threshold:
                                return False
                        except (ValueError, TypeError):
                            # Se volume for inválido, ignora o filtro de liquidez
                            continue

            if not found_any:
                return False

        return True

    def _get_pair_liquidity_score(
        self,
        tickers: dict[str, dict[str, str]],
        asset_from: str,
        asset_to: str,
    ) -> float:
        """Calcula um score de liquidez para um par de ativos.

        Args:
            tickers (dict): Dicionário de tickers
            asset_from (str): Ativo de origem
            asset_to (str): Ativo de destino

        Returns:
            float: Score de liquidez (maior = mais líquido)

        """
        # Suporta símbolos com e sem underscore
        candidate_symbols = [
            f"{asset_from}{asset_to}",
            f"{asset_to}{asset_from}",
            f"{asset_from}_{asset_to}",
            f"{asset_to}_{asset_from}",
        ]

        for symbol in candidate_symbols:
            if symbol in tickers:
                ticker_data = tickers[symbol]
                if "Q" in ticker_data:  # Volume em 24h
                    try:
                        return float(ticker_data["Q"])
                    except (ValueError, TypeError):
                        return 0
                return 0

        return 0

    def _identify_volatile_pairs(self, tickers: dict[str, dict[str, str]]) -> set[str]:
        """Identifica pares com alta volatilidade que podem ter oportunidades.

        Args:
            tickers (dict): Dicionário de tickers

        Returns:
            set: Conjunto de ativos voláteis

        """
        volatile_assets = set()

        for symbol, ticker_data in tickers.items():
            if "P" in ticker_data:  # Percentual de mudança em 24h
                try:
                    change_percent = abs(float(ticker_data["P"]))
                    # Se mudança > 5% em 24h, considera volátil
                    if change_percent > 5.0:
                        # Extrai o ativo base
                        if symbol.endswith("USDT"):
                            base = symbol[:-4]
                        elif symbol.endswith("BTC"):
                            base = symbol[:-3]
                        else:
                            base = symbol[:-4]
                        volatile_assets.add(base)
                except (ValueError, KeyError):
                    continue

        return volatile_assets

    def _identify_wide_spread_pairs(
        self,
        tickers: dict[str, dict[str, str]],
    ) -> set[str]:
        """Identifica pares com spreads maiores que podem ter oportunidades.

        Args:
            tickers (dict): Dicionário de tickers

        Returns:
            set: Conjunto de ativos com spreads largos

        """
        wide_spread_assets = set()

        for symbol, ticker_data in tickers.items():
            if "b" in ticker_data and "a" in ticker_data:  # bid e ask
                try:
                    bid_price = float(ticker_data["b"])
                    ask_price = float(ticker_data["a"])

                    if bid_price > 0:
                        spread = (ask_price - bid_price) / bid_price
                        # Se spread > 0.1%, considera spread largo
                        if spread > 0.001:
                            # Extrai o ativo base
                            if symbol.endswith("USDT"):
                                base = symbol[:-4]
                            elif symbol.endswith("BTC"):
                                base = symbol[:-3]
                            else:
                                base = symbol[:-4]
                            wide_spread_assets.add(base)
                except (ValueError, KeyError):
                    continue

        return wide_spread_assets

    

    def calculate_trade(
        self,
        tickers: dict[str, dict[str, str]],
        order_books: dict[str, dict[str, list]],
        asset_from: str,
        asset_to: str,
        amount_from: float,
        use_maker: bool = False,
    ) -> float:
        """Calcula o resultado de uma única negociação com estratégia otimizada,
        priorizando dados do livro de ordens em tempo real.

        Args:
            tickers (dict): O dicionário de tickers (usado como fallback).
            order_books (dict): Cache de order books em tempo real.
            asset_from (str): Ativo de origem.
            asset_to (str): Ativo de destino.
            amount_from (float): Quantidade do ativo de origem.
            use_maker (bool): Se deve usar comissão maker (menor) quando possível.

        Returns:
            float: A quantidade do ativo de destino após a negociação e comissão.
                   Retorna 0 se a negociação não for possível.

        """
        # Suporta símbolos com e sem underscore
        candidate_forward = [f"{asset_from}{asset_to}", f"{asset_from}_{asset_to}"]
        candidate_reverse = [f"{asset_to}{asset_from}", f"{asset_to}_{asset_from}"]

        used_symbol = next((s for s in candidate_forward if s in tickers), None)
        direction = "forward"
        if not used_symbol:
            used_symbol = next((s for s in candidate_reverse if s in tickers), None)
            direction = "reverse"
        if not used_symbol:
            return 0.0

        commission = self.get_commission_for_symbol(used_symbol, use_maker)

        # Prioriza dados do Order Book se disponível
        if (
            used_symbol in order_books
            and order_books[used_symbol].get("bids")
            and order_books[used_symbol].get("asks")
        ):
            order_book = order_books[used_symbol]
            if direction == "forward":
                # Vender asset_from (base) para obter asset_to (quote) ao melhor bid
                # O melhor bid é o primeiro da lista [preço, quantidade]
                bid = float(order_book["bids"][0][0])
                if bid <= 0:
                    return 0.0
                result = amount_from * bid * (1 - commission)
            else:  # reverse
                # Comprar asset_to (base) usando asset_from (quote) ao melhor ask
                # O melhor ask é o primeiro da lista [preço, quantidade]
                ask = float(order_book["asks"][0][0])
                if ask <= 0:
                    return 0.0
                result = (amount_from / ask) * (1 - commission)
        else:
            # Fallback para dados de ticker se o order book não estiver disponível
            if use_maker:
                logging.debug(
                    f"Order book para {used_symbol} indisponível. Usando fallback de ticker, "
                    "o que simula uma ordem TAKER, ignorando a flag use_maker."
                )
            ticker = tickers.get(used_symbol)
            if not ticker:
                return 0.0

            if direction == "forward":
                bid = float(ticker.get("bidPrice", 0))
                if bid <= 0:
                    return 0.0
                result = amount_from * bid * (1 - commission)
            else:  # reverse
                ask = float(ticker.get("askPrice", 0))
                if ask <= 0:
                    return 0.0
                result = (amount_from / ask) * (1 - commission)

        # Verificação de notional via limites específicos do símbolo (best-effort)
        symbol_limits = self.get_symbol_limits(used_symbol)
        if symbol_limits:
            min_notional = symbol_limits.get("min_notional", self.min_notional)
            # Conservador: considera notional em quote aproximado
            if direction == "forward":
                notional = amount_from * float(
                    tickers.get(used_symbol, {}).get("bidPrice", 0) or 0,
                )
            else:
                notional = amount_from
            if notional < min_notional:
                logging.debug(
                    f"Transação {used_symbol} abaixo do notional mínimo: {notional} < {min_notional}",
                )
                return 0.0

        return result

    def calculate_path_profit(
        self,
        tickers: dict[str, dict[str, str]],
        order_books: dict,
        path: list[str],
        start_amount: float,
    ) -> dict[str, Any]:
        """Calcula o lucro de um caminho específico.

        Args:
            tickers (dict): O dicionário de tickers.
            order_books (dict): Cache de order books em tempo real.
            path (list): O caminho de ativos.
            start_amount (float): A quantidade inicial.

        Returns:
            dict: Informações sobre o lucro do caminho.

        """
        if len(path) < 2:
            return {"profit": 0, "profit_percent": 0, "final_amount": start_amount}

        current_amount = start_amount

        # Executa as transações do caminho
        for i in range(len(path) - 1):
            asset_from = path[i]
            asset_to = path[i + 1]

            # Calcula a transação
            new_amount = self.calculate_trade(
                tickers,
                order_books,
                asset_from,
                asset_to,
                current_amount,
            )
            if new_amount <= 0:
                return {"profit": 0, "profit_percent": 0, "final_amount": 0}

            current_amount = new_amount

        # Calcula o lucro
        profit = current_amount - start_amount
        profit_percent = (profit / start_amount) * 100 if start_amount > 0 else 0

        return {
            "profit": profit,
            "profit_percent": profit_percent,
            "final_amount": current_amount,
            "path": path,
            "initial_investment": start_amount,
            "returns_to_start": path[0] == path[-1],
        }

    @staticmethod
    def get_symbol_and_side(
        tickers: dict[str, dict[str, str]],
        asset_from: str,
        asset_to: str,
    ) -> tuple[str | None, str | None]:
        """Determina o símbolo de negociação e o lado da ordem (BUY/SELL).

        Esta função é estática porque sua lógica depende apenas dos tickers, não do estado
        da instância do DataAnalyzer.

        Args:
            tickers (dict): O dicionário de tickers atual.
            asset_from (str): Ativo de origem (o que você tem).
            asset_to (str): Ativo de destino (o que você quer).

        Returns:
            tuple[str | None, str | None]: Uma tupla contendo o símbolo e o lado ('BUY' ou 'SELL').
                                         Retorna (None, None) se o par não for encontrado.

        """
        # Suporta símbolos com e sem underscore
        forward_candidates = [f"{asset_from}{asset_to}", f"{asset_from}_{asset_to}"]
        for sym in forward_candidates:
            if sym in tickers:
                return sym, "SELL"

        backward_candidates = [f"{asset_to}{asset_from}", f"{asset_to}_{asset_from}"]
        for sym in backward_candidates:
            if sym in tickers:
                return sym, "BUY"

        return None, None
