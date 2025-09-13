"""Módulo para gerenciamento de risco, alocação de capital e dimensionamento de ordens.
Implementa a lógica Hydra 2.0 para otimização avançada de capital.
"""

import logging
import time
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Any

from api_client import ApiClient
from data_analyzer import DataAnalyzer


@dataclass
class PathAnalysis:
    """Análise detalhada de um caminho de arbitragem."""

    path_info: dict
    expected_profit: Decimal
    risk_score: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    execution_probability: Decimal
    correlation_score: Decimal


@dataclass
class PortfolioAllocation:
    """Alocação otimizada de portfólio para múltiplos caminhos."""

    path_allocations: list[dict[str, Any]]
    total_expected_profit: Decimal
    portfolio_risk_score: Decimal
    diversification_score: Decimal
    execution_strategy: str


class RiskManager:
    """Gerencia o risco, decide a alocação de capital e o tamanho das ordens.
    Implementa a lógica Hydra 2.0 para otimização avançada de capital.
    """

    def __init__(self, api_client: ApiClient, data_analyzer: DataAnalyzer):
        """Inicializa o gerenciador de risco.

        Args:
            api_client (ApiClient): O cliente da API para buscar dados da conta/exchange.
            data_analyzer (DataAnalyzer): O analisador de dados para acessar a lógica de negociação.

        """
        self.api_client = api_client
        self.data_analyzer = data_analyzer
        self.exchange_info = None

        # Parâmetros dinâmicos - serão obtidos da API
        self.trading_parameters = None
        self.risk_free_rate = Decimal(
            "0.02",
        )  # 2% ao ano (pode ser ajustado dinamicamente)
        self.max_correlation_threshold = Decimal("0.7")
        self.min_sharpe_ratio = Decimal("0.5")

        # Configurações de risco - serão obtidas dinamicamente
        self.max_portfolio_risk = Decimal("0.05")  # 5% máximo de risco por operação
        self.max_daily_loss = Decimal("0.02")  # 2% máximo de perda diária
        self.position_sizing_method = "kelly"  # 'kelly', 'fixed', 'volatility'
        self.stop_loss_percentage = Decimal("0.01")  # 1% stop-loss
        self.take_profit_percentage = Decimal("0.02")  # 2% take-profit
        self.max_concurrent_positions = 5
        self.min_position_size = Decimal(10)  # Valor mínimo em USDT

        # Histórico de operações para gestão de risco
        self.daily_pnl = Decimal(0)
        self.open_positions = []
        self.position_history = []

        # Inicializa parâmetros dinâmicos
        self._initialize_dynamic_parameters()

    def _initialize_dynamic_parameters(self):
        """Inicializa parâmetros de risco dinamicamente da API da Binance."""
        # Esta função pode ser expandida para carregar parâmetros de um arquivo de configuração ou API.
        logging.info("🔧 Carregando parâmetros de risco padrão. (Implementação dinâmica de risco pendente)")
        # Os valores padrão definidos em __init__ serão usados.
        pass

    def get_dynamic_risk_parameters(self) -> dict[str, Any]:
        """Obtém parâmetros de risco dinâmicos baseados em condições de mercado atuais.

        Returns:
            dict: Parâmetros de risco ajustados dinamicamente.

        """
        try:
            # Obtém métricas de qualidade do mercado
            metrics = self.api_client.get_market_quality_metrics()

            if metrics:
                avg_volatility = sum(
                    s.get("volatility", 0.05)
                    for s in metrics.get("symbols", {}).values()
                )
                symbol_count = len(metrics.get("symbols", {}))
                if symbol_count > 0:
                    avg_volatility /= symbol_count

                # Ajusta parâmetros baseado na volatilidade
                volatility_multiplier = min(
                    2.0,
                    max(0.5, avg_volatility / 0.05),
                )  # Normalizado para 5%

                dynamic_params = {
                    "max_portfolio_risk": float(self.max_portfolio_risk)
                    * volatility_multiplier,
                    "max_daily_loss": float(self.max_daily_loss)
                    * volatility_multiplier,
                    "stop_loss_percentage": float(self.stop_loss_percentage)
                    * volatility_multiplier,
                    "take_profit_percentage": float(self.take_profit_percentage)
                    * volatility_multiplier,
                    "max_concurrent_positions": max(
                        1,
                        int(self.max_concurrent_positions / volatility_multiplier),
                    ),
                    "volatility_adjustment": volatility_multiplier,
                }

                logging.info(
                    f"Parâmetros de risco ajustados dinamicamente (volatilidade: {avg_volatility:.3f}, multiplicador: {volatility_multiplier:.2f})",
                )
                return dynamic_params
            return {
                "max_portfolio_risk": float(self.max_portfolio_risk),
                "max_daily_loss": float(self.max_daily_loss),
                "stop_loss_percentage": float(self.stop_loss_percentage),
                "take_profit_percentage": float(self.take_profit_percentage),
                "max_concurrent_positions": self.max_concurrent_positions,
                "volatility_adjustment": 1.0,
            }

        except Exception as e:
            logging.exception(f"Erro ao obter parâmetros de risco dinâmicos: {e}")
            return {
                "max_portfolio_risk": float(self.max_portfolio_risk),
                "max_daily_loss": float(self.max_daily_loss),
                "stop_loss_percentage": float(self.stop_loss_percentage),
                "take_profit_percentage": float(self.take_profit_percentage),
                "max_concurrent_positions": self.max_concurrent_positions,
                "volatility_adjustment": 1.0,
            }

    def _fetch_exchange_info_if_needed(self):
        """Busca e armazena as informações da exchange se ainda não o fez."""
        if not self.exchange_info:
            logging.info("Buscando informações da exchange para o RiskManager...")
            self.exchange_info = self.api_client.get_exchange_info()
            if not self.exchange_info:
                logging.error("Falha ao buscar informações da exchange no RiskManager.")

    def get_balance(self, asset: str) -> Decimal:
        """Obtém o saldo livre de um ativo específico da conta.

        Args:
            asset (str): O ticker do ativo (ex: 'BTC', 'USDT').

        Returns:
            Decimal: O saldo livre do ativo. Retorna Decimal('0.0') se não for encontrado.

        """
        try:
            account_info = self.api_client.get_account_info()
            if not account_info or "balances" not in account_info:
                logging.warning("Não foi possível obter informações da conta.")
                return Decimal("0.0")

            for balance in account_info["balances"]:
                if balance["asset"] == asset:
                    return Decimal(balance["free"])

            logging.warning(f"Ativo {asset} não encontrado nos saldos da conta.")
            return Decimal("0.0")
        except Exception as e:
            logging.exception(f"Erro ao obter saldo para {asset}: {e}")
            return Decimal("0.0")

    def get_symbol_filters(self, symbol: str) -> list[dict[str, Any]] | None:
        """Obtém todos os filtros para um símbolo.

        Args:
            symbol (str): O símbolo (ex: 'BTCUSDT').

        Returns:
            list[dict] | None: A lista de filtros ou None se não for encontrado.

        """
        self._fetch_exchange_info_if_needed()
        if not self.exchange_info or "symbols" not in self.exchange_info:
            return None

        for s in self.exchange_info["symbols"]:
            if s["symbol"] == symbol:
                return s["filters"]
        return None

    def _analyze_path_risk(
        self,
        path_info: dict,
        investment_size: Decimal,
        tickers: dict,
        order_books: dict,
    ) -> PathAnalysis:
        """Analisa o risco e retorno de um caminho específico.

        Args:
            path_info (dict): Informações do caminho.
            investment_size (Decimal): Tamanho do investimento.
            tickers (dict): Dados de mercado atuais.
            order_books (dict): Cache de order books em tempo real.

        Returns:
            PathAnalysis: Análise detalhada do caminho.

        """
        path = path_info["path"]
        expected_profit = self._calculate_path_absolute_profit(
            path_info,
            investment_size,
            tickers,
            order_books,
        )

        # Calcula métricas de risco
        risk_score = self._calculate_path_risk_score(path, tickers)
        volatility = self._estimate_path_volatility(path, tickers)
        sharpe_ratio = self._calculate_sharpe_ratio(
            expected_profit,
            volatility,
            investment_size,
        )
        max_drawdown = self._estimate_max_drawdown(path, tickers)
        execution_probability = self._calculate_execution_probability(path, tickers)
        correlation_score = self._calculate_correlation_score(path, tickers)

        return PathAnalysis(
            path_info=path_info,
            expected_profit=expected_profit,
            risk_score=risk_score,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            execution_probability=execution_probability,
            correlation_score=correlation_score,
        )

    def _calculate_path_risk_score(self, path: list[str], tickers: dict) -> Decimal:
        """Calcula o score de risco de um caminho baseado na complexidade e volatilidade.

        Args:
            path (List[str]): Lista de ativos no caminho.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Score de risco (0-1, onde 1 é mais arriscado).

        """
        if len(path) <= 2:
            return Decimal("0.3")  # Caminhos simples são menos arriscados

        # Caminhos mais longos têm mais pontos de falha
        complexity_risk = Decimal(str(len(path) - 2)) * Decimal("0.1")

        # Verifica volatilidade dos pares envolvidos
        volatility_risk = Decimal(0)
        for i in range(len(path) - 1):
            asset_from, asset_to = path[i], path[i + 1]
            try:
                symbol, _ = self.data_analyzer.get_symbol_and_side(
                    tickers,
                    asset_from,
                    asset_to,
                )
                volatility_risk += self._estimate_spread(symbol, tickers)
            except (TypeError, ValueError):
                # Se o par não for encontrado, adiciona uma penalidade de risco
                volatility_risk += Decimal("0.05")

        total_risk = min(Decimal("1.0"), complexity_risk + volatility_risk)
        return total_risk

    def _estimate_spread(self, symbol: str, tickers: dict) -> Decimal:
        """Estima o spread bid-ask como proxy para volatilidade.

        Args:
            symbol (str): Símbolo do par.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Estimativa do spread.

        """
        if symbol not in tickers:
            return Decimal("0.01")  # Spread padrão de 1%

        ticker_data = tickers[symbol]
        if "bidPrice" in ticker_data and "askPrice" in ticker_data:
            try:
                bid = Decimal(ticker_data["bidPrice"])
                ask = Decimal(ticker_data["askPrice"])
                if bid > 0:
                    return (ask - bid) / bid
            except (InvalidOperation, ValueError):
                return Decimal(
                    "0.01",
                )  # Retorna spread padrão em caso de erro de conversão
        return Decimal("0.01")

    def _estimate_path_volatility(self, path: list[str], tickers: dict) -> Decimal:
        """Estima a volatilidade de um caminho baseado nos spreads dos pares.

        Args:
            path (List[str]): Lista de ativos no caminho.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Estimativa de volatilidade.

        """
        total_volatility = Decimal(0)
        for i in range(len(path) - 1):
            asset_from, asset_to = path[i], path[i + 1]
            symbol, _ = self.data_analyzer.get_symbol_and_side(
                tickers,
                asset_from,
                asset_to,
            )
            if symbol:
                spread = self._estimate_spread(symbol, tickers)
                total_volatility += spread

        return total_volatility / max(1, len(path) - 1)

    def _calculate_sharpe_ratio(
        self,
        expected_profit: Decimal,
        volatility: Decimal,
        investment: Decimal,
    ) -> Decimal:
        """Calcula o Sharpe ratio de um caminho.

        Args:
            expected_profit (Decimal): Lucro esperado.
            volatility (Decimal): Volatilidade estimada.
            investment (Decimal): Investimento inicial.

        Returns:
            Decimal: Sharpe ratio.

        """
        if volatility <= 0 or investment <= 0:
            return Decimal(0)

        excess_return = expected_profit - (
            investment * self.risk_free_rate / Decimal(365)
        )
        return excess_return / (volatility * investment)

    def _estimate_max_drawdown(self, path: list[str], tickers: dict) -> Decimal:
        """Estima o máximo drawdown baseado na complexidade do caminho.

        Args:
            path (List[str]): Lista de ativos no caminho.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Estimativa de máximo drawdown.

        """
        # Drawdown estimado baseado no número de transações
        base_drawdown = Decimal("0.02")  # 2% base
        transaction_penalty = Decimal(str(len(path) - 1)) * Decimal(
            "0.005",
        )  # 0.5% por transação
        return min(Decimal("0.1"), base_drawdown + transaction_penalty)  # Máximo 10%

    def _calculate_execution_probability(
        self,
        path: list[str],
        tickers: dict,
    ) -> Decimal:
        """Calcula a probabilidade de execução bem-sucedida do caminho.

        Args:
            path (List[str]): Lista de ativos no caminho.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Probabilidade de execução (0-1).

        """
        base_probability = Decimal("0.95")  # 95% base

        # Penalidade por complexidade
        complexity_penalty = Decimal(str(len(path) - 2)) * Decimal("0.02")

        # Penalidade por spreads altos
        spread_penalty = Decimal(0)
        for i in range(len(path) - 1):
            asset_from, asset_to = path[i], path[i + 1]
            symbol, _ = self.data_analyzer.get_symbol_and_side(
                tickers,
                asset_from,
                asset_to,
            )
            if symbol:
                spread = self._estimate_spread(symbol, tickers)
                if spread > Decimal("0.02"):  # Spread > 2%
                    spread_penalty += Decimal("0.01")

        final_probability = base_probability - complexity_penalty - spread_penalty
        return max(Decimal("0.5"), min(Decimal("1.0"), final_probability))

    def _calculate_correlation_score(self, path: list[str], tickers: dict) -> Decimal:
        """Calcula o score de correlação do caminho com outros caminhos.

        Args:
            path (List[str]): Lista de ativos no caminho.
            tickers (dict): Dados de mercado.

        Returns:
            Decimal: Score de correlação (0-1, onde 1 é alta correlação).

        """
        # Implementação simplificada - caminhos que compartilham ativos têm alta correlação
        unique_assets = set(path)
        if len(unique_assets) <= 2:
            return Decimal("0.3")  # Caminhos simples têm baixa correlação
        return Decimal("0.6")  # Caminhos complexos têm correlação média

    def _optimize_portfolio_allocation(
        self,
        path_analyses: list[PathAnalysis],
        total_capital: Decimal,
    ) -> PortfolioAllocation:
        """Otimiza a alocação de capital entre múltiplos caminhos usando a lógica Hydra 2.0.

        Args:
            path_analyses (List[PathAnalysis]): Análises dos caminhos disponíveis.
            total_capital (Decimal): Capital total disponível.

        Returns:
            PortfolioAllocation: Alocação otimizada do portfólio.

        """
        if not path_analyses:
            return PortfolioAllocation([], Decimal(0), Decimal(0), Decimal(0), "none")

        # Filtra caminhos que atendem aos critérios mínimos
        viable_paths = [
            pa
            for pa in path_analyses
            if pa.sharpe_ratio >= self.min_sharpe_ratio
            and pa.execution_probability >= Decimal("0.7")
        ]

        if not viable_paths:
            return PortfolioAllocation([], Decimal(0), Decimal(0), Decimal(0), "none")

        # Estratégia 1: Caminho único com melhor Sharpe ratio
        best_single_path = max(viable_paths, key=lambda x: x.sharpe_ratio)
        single_allocation = [
            {
                "path_info": best_single_path.path_info,
                "investment_size": total_capital,
                "expected_profit": best_single_path.expected_profit,
                "risk_score": best_single_path.risk_score,
            },
        ]

        # Estratégia 2: Portfólio diversificado
        diversified_paths = self._select_diversified_paths(viable_paths)
        if len(diversified_paths) > 1:
            diversified_allocation = self._calculate_diversified_allocation(
                diversified_paths,
                total_capital,
            )

            # Compara as estratégias
            single_total_profit = best_single_path.expected_profit
            diversified_total_profit = sum(
                pa.expected_profit for pa in diversified_paths
            )

            if diversified_total_profit > single_total_profit * Decimal(
                "1.1",
            ):  # 10% melhor
                return PortfolioAllocation(
                    path_allocations=diversified_allocation,
                    total_expected_profit=diversified_total_profit,
                    portfolio_risk_score=self._calculate_portfolio_risk(
                        diversified_paths,
                    ),
                    diversification_score=self._calculate_diversification_score(
                        diversified_paths,
                    ),
                    execution_strategy="diversified",
                )

        # Retorna estratégia de caminho único
        return PortfolioAllocation(
            path_allocations=single_allocation,
            total_expected_profit=best_single_path.expected_profit,
            portfolio_risk_score=best_single_path.risk_score,
            diversification_score=Decimal(0),
            execution_strategy="single",
        )

    def _select_diversified_paths(
        self,
        path_analyses: list[PathAnalysis],
    ) -> list[PathAnalysis]:
        """Seleciona caminhos diversificados com baixa correlação.

        Args:
            path_analyses (List[PathAnalysis]): Análises dos caminhos.

        Returns:
            List[PathAnalysis]: Caminhos selecionados para diversificação.

        """
        selected_paths = []
        for pa in sorted(path_analyses, key=lambda x: x.sharpe_ratio, reverse=True):
            # Verifica correlação com caminhos já selecionados
            max_correlation = max(
                (pa.correlation_score for pa in selected_paths),
                default=Decimal(0),
            )

            if max_correlation <= self.max_correlation_threshold:
                selected_paths.append(pa)
                if len(selected_paths) >= 3:  # Máximo 3 caminhos para diversificação
                    break

        return selected_paths

    def _calculate_diversified_allocation(
        self,
        path_analyses: list[PathAnalysis],
        total_capital: Decimal,
    ) -> list[dict]:
        """Calcula alocação de capital para caminhos diversificados.

        Args:
            path_analyses (List[PathAnalysis]): Caminhos selecionados.
            total_capital (Decimal): Capital total.

        Returns:
            List[Dict]: Alocações de capital.

        """
        # Alocação baseada no Sharpe ratio
        total_sharpe = sum(pa.sharpe_ratio for pa in path_analyses)
        allocations = []

        for pa in path_analyses:
            allocation_ratio = pa.sharpe_ratio / total_sharpe
            investment_size = total_capital * allocation_ratio

            allocations.append(
                {
                    "path_info": pa.path_info,
                    "investment_size": investment_size,
                    "expected_profit": pa.expected_profit * allocation_ratio,
                    "risk_score": pa.risk_score,
                },
            )

        return allocations

    def _calculate_portfolio_risk(self, path_analyses: list[PathAnalysis]) -> Decimal:
        """Calcula o risco total do portfólio.

        Args:
            path_analyses (List[PathAnalysis]): Análises dos caminhos.

        Returns:
            Decimal: Score de risco do portfólio.

        """
        if not path_analyses:
            return Decimal(0)

        # Risco médio ponderado
        total_risk = sum(pa.risk_score for pa in path_analyses)
        return total_risk / len(path_analyses)

    def _calculate_diversification_score(
        self,
        path_analyses: list[PathAnalysis],
    ) -> Decimal:
        """Calcula o score de diversificação do portfólio.

        Args:
            path_analyses (List[PathAnalysis]): Análises dos caminhos.

        Returns:
            Decimal: Score de diversificação (0-1).

        """
        if len(path_analyses) <= 1:
            return Decimal(0)

        # Score baseado no número de caminhos e baixa correlação
        correlation_penalty = sum(pa.correlation_score for pa in path_analyses) / len(
            path_analyses,
        )
        diversification_bonus = Decimal(str(len(path_analyses))) * Decimal("0.2")

        return min(Decimal("1.0"), diversification_bonus - correlation_penalty)

    def generate_trade_instructions(
        self,
        profitable_paths: list[dict],
        risk_percentage: float,
        tickers: dict,
        order_books: dict,
    ) -> list[dict]:
        """Analisa as oportunidades e gera instruções de negociação concretas usando a lógica Hydra 2.0.

        Args:
            profitable_paths (list[dict]): Lista de caminhos lucrativos do DataAnalyzer.
            risk_percentage (float): A porcentagem do saldo a ser arriscada (ex: 0.01 para 1%).
            tickers (dict): Os tickers atuais para simulação de lucro.

        Returns:
            list[dict]: Uma lista de instruções de negociação.

        """
        # Exemplo de como dados de ativos podem ser usados para análise de risco avançada
        asset_details = self.api_client.get_asset_details()
        if asset_details:
            logging.info(
                f"Detalhes de ativos obtidos para análise de risco avançada. Total de ativos: {len(asset_details)}",
            )
            # Lógica futura poderia verificar 'depositStatus', 'withdrawStatus' etc.
            # dos ativos no `profitable_paths` para ajustar o risco.

        if not profitable_paths:
            return []

        # FILOSOFIA HYDRA: Agrupa caminhos por ativo inicial para otimização de capital
        paths_by_start_asset = {}
        for path_info in profitable_paths:
            start_asset = path_info["path"][0]
            if start_asset not in paths_by_start_asset:
                paths_by_start_asset[start_asset] = []
            paths_by_start_asset[start_asset].append(path_info)

        logging.info(
            f"🔍 Caminhos agrupados por ativo inicial: {list(paths_by_start_asset.keys())}",
        )

        # FILOSOFIA HYDRA: Analisa cada ativo inicial separadamente
        all_instructions = []
        assets_with_balance = []

        for start_asset, asset_paths in paths_by_start_asset.items():
            logging.info(
                f"🎯 Analisando {len(asset_paths)} caminhos a partir de {start_asset}",
            )

            # Calcula capital disponível para este ativo específico
            total_capital = self.calculate_investment_size(start_asset, risk_percentage)
            if total_capital <= 0:
                logging.warning(
                    f"Capital insuficiente de {start_asset} para iniciar a negociação.",
                )
                continue

            assets_with_balance.append(start_asset)
            logging.info(f"💰 Capital disponível para {start_asset}: {total_capital}")

            # HYDRA 2.0: Análise avançada de todos os caminhos deste ativo (retorno e avanço)
            path_analyses = []
            return_paths = []
            forward_paths = []

            for path_info in asset_paths:
                analysis = self._analyze_path_risk(
                    path_info,
                    total_capital / len(asset_paths),
                    tickers,
                    order_books,
                )
                path_analyses.append(analysis)

                # Filosofia Hydra: Separa caminhos que retornam ao início e caminhos que terminam em outros ativos
                # O objetivo é maximizar o lucro total, não privilegiar caminhos triangulares
                if path_info.get("returns_to_start", False):
                    return_paths.append(analysis)
                else:
                    forward_paths.append(analysis)

            logging.info(
                f"🔍 HYDRA 2.0 para {start_asset}: {len(return_paths)} caminhos de retorno, {len(forward_paths)} caminhos de avanço",
            )

            # HYDRA 2.0: Otimização de portfólio considerando todos os caminhos lucrativos deste ativo
            portfolio_allocation = self._optimize_portfolio_allocation_hydra(
                return_paths,
                forward_paths,
                total_capital,
            )

            if portfolio_allocation.path_allocations:
                # Log das decisões de alocação para este ativo
                logging.info(
                    f"Estratégia Hydra 2.0 para {start_asset}: {portfolio_allocation.execution_strategy}",
                )
                logging.info(
                    f"Lucro Total Esperado: {portfolio_allocation.total_expected_profit:.8f} {start_asset}",
                )
                logging.info(
                    f"Risco do Portfólio: {portfolio_allocation.portfolio_risk_score:.4f}",
                )
                logging.info(
                    f"Score de Diversificação: {portfolio_allocation.diversification_score:.4f}",
                )

                all_instructions.extend(portfolio_allocation.path_allocations)
            else:
                logging.info(
                    f"Nenhuma estratégia de execução lucrativa foi encontrada para {start_asset}.",
                )

        # Verifica se pelo menos um ativo tem saldo suficiente
        if not assets_with_balance:
            logging.warning(
                "⚠️ Nenhum ativo tem saldo suficiente para operações. Considere depositar fundos.",
            )
            logging.info("💡 Dica: Para testar o sistema, você pode:")
            logging.info("   1. Depositar uma pequena quantidade de USDT ou BNB")
            logging.info("   2. Usar o modo --dry-run para simular operações")
            logging.info(
                "   3. Ajustar o risk_percentage para valores menores (ex: 0.001 para 0.1%)",
            )

        return all_instructions

    def calculate_investment_size(self, asset: str, risk_percentage: float) -> Decimal:
        """Calcula o tamanho do investimento inicial com base no saldo e risco.

        Args:
            asset (str): O ativo para o investimento.
            risk_percentage (float): A porcentagem do saldo a arriscar.

        Returns:
            Decimal: A quantidade do ativo a ser investida.

        """
        balance = self.get_balance(asset)
        if balance <= 0:
            return Decimal(0)

        # Obtém parâmetros de risco dinâmicos
        dynamic_params = self.get_dynamic_risk_parameters()
        max_portfolio_risk = Decimal(
            str(dynamic_params.get("max_portfolio_risk", 0.05)),
        )

        # Ajusta risk_percentage baseado nos parâmetros dinâmicos
        adjusted_risk = min(risk_percentage, float(max_portfolio_risk))

        # Calcula o investimento baseado na porcentagem de risco ajustada
        investment = (balance * Decimal(str(adjusted_risk))).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )

        # FILOSOFIA HYDRA: Permite operações mesmo com saldos baixos
        # Se o investimento calculado for muito pequeno, usa o saldo total disponível
        if investment < Decimal("0.0001"):  # Menos que 0.0001 do ativo
            investment = balance
            logging.info(
                f"💰 Investimento muito pequeno para {asset}, usando saldo total: {investment}",
            )

        # Verifica se atende ao tamanho mínimo de posição
        if investment < self.min_position_size:
            logging.warning(
                f"⚠️ Investimento {investment} {asset} abaixo do mínimo {self.min_position_size} USDT",
            )
            return Decimal(0)

        logging.info(
            f"💰 Investimento calculado para {asset}: {investment} (risco: {adjusted_risk:.3f})",
        )
        return investment

    def adjust_quantity_to_filters(self, symbol: str, quantity: Decimal) -> Decimal:
        """Ajusta a quantidade de uma ordem para cumprir as regras dos filtros (ex: LOT_SIZE).

        Args:
            symbol (str): O símbolo da negociação (ex: 'BTCUSDT').
            quantity (Decimal): A quantidade calculada.

        Returns:
            Decimal: A quantidade ajustada, ou Decimal('0') se não atender aos critérios.

        """
        filters = self.get_symbol_filters(symbol)
        if not filters:
            logging.warning(
                f"Não foi possível obter filtros para o símbolo {symbol}. A ordem pode falhar.",
            )
            return quantity

        lot_size_filter = next(
            (f for f in filters if f["filterType"] == "LOT_SIZE"),
            None,
        )
        if not lot_size_filter:
            return quantity

        min_qty = Decimal(lot_size_filter["minQty"])
        max_qty = Decimal(lot_size_filter["maxQty"])
        step_size = Decimal(lot_size_filter["stepSize"])

        if quantity < min_qty:
            return Decimal(0)

        quantity = min(quantity, max_qty)

        # Ajusta a quantidade para o step_size
        adjusted_quantity = (quantity - min_qty) // step_size * step_size + min_qty
        return adjusted_quantity.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

    def _calculate_path_absolute_profit(
        self,
        path_info: dict,
        investment_size: Decimal,
        tickers: dict,
        order_books: dict,
    ) -> Decimal:
        """Calcula o lucro absoluto de um único caminho, simulando a execução e os filtros.

        Args:
            path_info (dict): A informação do caminho.
            investment_size (Decimal): O capital inicial.
            tickers (dict): Os tickers atuais.
            order_books (dict): Cache de order books em tempo real.

        Returns:
            Decimal: O lucro (ou prejuízo) absoluto.

        """
        path = path_info["path"]
        current_amount = investment_size

        for i in range(len(path) - 1):
            asset_from = path[i]
            asset_to = path[i + 1]

            symbol, side = self.data_analyzer.get_symbol_and_side(
                tickers,
                asset_from,
                asset_to,
            )
            if not symbol:
                logging.error(
                    f"[SIMULAÇÃO] Não foi possível determinar o símbolo para {asset_from}->{asset_to}.",
                )
                return Decimal(0)

            adjusted_quantity = self.adjust_quantity_to_filters(symbol, current_amount)
            if adjusted_quantity <= 0:
                logging.warning(
                    f"[SIMULAÇÃO] Quantidade ajustada para {symbol} é zero. Caminho inviável.",
                )
                return Decimal(0)

            try:
                current_amount = self.data_analyzer.calculate_trade(
                    tickers,
                    order_books,
                    asset_from,
                    asset_to,
                    float(adjusted_quantity),
                )
                current_amount = Decimal(str(current_amount))
            except (KeyError, ZeroDivisionError) as e:
                logging.exception(
                    f"[SIMULAÇÃO] Erro ao calcular o passo {asset_from}->{asset_to}: {e}",
                )
                return Decimal(0)

        return current_amount - investment_size

    def calculate_kelly_position_size(
        self,
        win_rate: Decimal,
        avg_win: Decimal,
        avg_loss: Decimal,
    ) -> Decimal:
        """Calcula o tamanho da posição usando o Critério de Kelly.

        Args:
            win_rate (Decimal): Taxa de vitória (0-1).
            avg_win (Decimal): Ganho médio por operação vencedora.
            avg_loss (Decimal): Perda média por operação perdedora.

        Returns:
            Decimal: Porcentagem do capital a ser alocada.

        """
        if avg_loss == 0:
            return Decimal(0)

        kelly_fraction = (
            win_rate * avg_win - (Decimal(1) - win_rate) * avg_loss
        ) / avg_win

        # Limita o Kelly a 25% do capital para evitar risco excessivo
        return max(Decimal(0), min(Decimal("0.25"), kelly_fraction))

    def calculate_volatility_position_size(
        self,
        volatility: Decimal,
        target_risk: Decimal,
    ) -> Decimal:
        """Calcula o tamanho da posição baseado na volatilidade.

        Args:
            volatility (Decimal): Volatilidade estimada do ativo.
            target_risk (Decimal): Risco alvo em porcentagem.

        Returns:
            Decimal: Porcentagem do capital a ser alocada.

        """
        if volatility == 0:
            return Decimal(0)

        position_size = target_risk / volatility
        return max(Decimal(0), min(Decimal("0.5"), position_size))

    def calculate_dynamic_position_size(
        self,
        path_analysis: PathAnalysis,
        total_capital: Decimal,
    ) -> Decimal:
        """Calcula o tamanho dinâmico da posição baseado no método configurado.

        Args:
            path_analysis (PathAnalysis): Análise do caminho.
            total_capital (Decimal): Capital total disponível.

        Returns:
            Decimal: Tamanho da posição em unidades do ativo.

        """
        if self.position_sizing_method == "kelly":
            # Usa dados históricos para calcular Kelly
            win_rate = self._calculate_historical_win_rate()
            avg_win = self._calculate_average_win()
            avg_loss = self._calculate_average_loss()

            kelly_fraction = self.calculate_kelly_position_size(
                win_rate,
                avg_win,
                avg_loss,
            )
            return total_capital * kelly_fraction

        if self.position_sizing_method == "volatility":
            # Usa volatilidade para dimensionar
            volatility = path_analysis.max_drawdown
            target_risk = self.max_portfolio_risk

            volatility_fraction = self.calculate_volatility_position_size(
                volatility,
                target_risk,
            )
            return total_capital * volatility_fraction

        # 'fixed'
        # Usa risco fixo
        return total_capital * self.max_portfolio_risk

    def _calculate_historical_win_rate(self) -> Decimal:
        """Calcula a taxa de vitória histórica.

        Returns:
            Decimal: Taxa de vitória (0-1).

        """
        if not self.position_history:
            return Decimal("0.5")  # Taxa neutra se não há histórico

        winning_trades = sum(1 for pos in self.position_history if pos["pnl"] > 0)
        total_trades = len(self.position_history)

        return Decimal(str(winning_trades)) / Decimal(str(total_trades))

    def _calculate_average_win(self) -> Decimal:
        """Calcula o ganho médio por operação vencedora.

        Returns:
            Decimal: Ganho médio.

        """
        winning_trades = [pos for pos in self.position_history if pos["pnl"] > 0]

        if not winning_trades:
            return Decimal("0.02")  # 2% padrão

        total_win = sum(pos["pnl"] for pos in winning_trades)
        return total_win / len(winning_trades)

    def _calculate_average_loss(self) -> Decimal:
        """Calcula a perda média por operação perdedora.

        Returns:
            Decimal: Perda média.

        """
        losing_trades = [pos for pos in self.position_history if pos["pnl"] < 0]

        if not losing_trades:
            return Decimal("0.01")  # 1% padrão

        total_loss = sum(abs(pos["pnl"]) for pos in losing_trades)
        return total_loss / len(losing_trades)

    def check_risk_limits(
        self,
        new_position_size: Decimal,
        path_analysis: PathAnalysis,
    ) -> bool:
        """Verifica se uma nova posição respeita os limites de risco.

        Args:
            new_position_size (Decimal): Tamanho da nova posição.
            path_analysis (PathAnalysis): Análise do caminho.

        Returns:
            bool: True se os limites de risco são respeitados.

        """
        # Verifica limite de perda diária
        if self.daily_pnl < -self.max_daily_loss:
            logging.warning("Limite de perda diária atingido. Negociação bloqueada.")
            return False

        # Verifica número máximo de posições simultâneas
        if len(self.open_positions) >= self.max_concurrent_positions:
            logging.warning("Número máximo de posições simultâneas atingido.")
            return False

        # Verifica tamanho mínimo da posição
        if new_position_size < self.min_position_size:
            logging.warning(
                f"Posição muito pequena: {new_position_size}. Mínimo: {self.min_position_size}",
            )
            return False

        # Verifica risco máximo por posição
        position_risk = path_analysis.max_drawdown * new_position_size
        if position_risk > self.max_portfolio_risk:
            logging.warning(f"Risco da posição muito alto: {position_risk:.4f}")
            return False

        return True

    def add_position(
        self,
        path: list[str],
        position_size: Decimal,
        entry_price: Decimal,
    ):
        """Adiciona uma nova posição ao histórico.

        Args:
            path (List[str]): Caminho da arbitragem.
            position_size (Decimal): Tamanho da posição.
            entry_price (Decimal): Preço de entrada.

        """
        position = {
            "id": len(self.open_positions) + 1,
            "path": path,
            "size": position_size,
            "entry_price": entry_price,
            "entry_time": time.time(),
            "stop_loss": entry_price * (Decimal(1) - self.stop_loss_percentage),
            "take_profit": entry_price * (Decimal(1) + self.take_profit_percentage),
            "pnl": Decimal(0),
            "status": "open",
        }

        self.open_positions.append(position)
        logging.info(f"Nova posição aberta: {position['id']} - {path}")

    def close_position(self, position_id: int, exit_price: Decimal, pnl: Decimal):
        """Fecha uma posição e atualiza o histórico.

        Args:
            position_id (int): ID da posição.
            exit_price (Decimal): Preço de saída.
            pnl (Decimal): Lucro/prejuízo da operação.

        """
        for i, position in enumerate(self.open_positions):
            if position["id"] == position_id:
                position["exit_price"] = exit_price
                position["exit_time"] = time.time()
                position["pnl"] = pnl
                position["status"] = "closed"

                # Move para histórico
                self.position_history.append(position)
                self.open_positions.pop(i)

                # Atualiza PnL diário
                self.daily_pnl += pnl

                logging.info(f"Posição {position_id} fechada. PnL: {pnl:.8f}")
                break

    def check_stop_loss_take_profit(self, current_prices: dict) -> list[dict]:
        """Verifica se alguma posição atingiu stop-loss ou take-profit.

        Args:
            current_prices (dict): Preços atuais dos ativos.

        Returns:
            List[dict]: Lista de posições que devem ser fechadas.

        """
        positions_to_close = []

        for position in self.open_positions:
            # Determina o preço atual do ativo final do caminho
            final_asset = position["path"][-1]
            current_price = self._get_current_price(final_asset, current_prices)

            if current_price is None:
                continue

            # Verifica stop-loss
            if current_price <= position["stop_loss"]:
                positions_to_close.append(
                    {
                        "position": position,
                        "reason": "stop_loss",
                        "price": current_price,
                    },
                )

            # Verifica take-profit
            elif current_price >= position["take_profit"]:
                positions_to_close.append(
                    {
                        "position": position,
                        "reason": "take_profit",
                        "price": current_price,
                    },
                )

        return positions_to_close

    def _get_current_price(self, asset: str, current_prices: dict) -> Decimal | None:
        """Obtém o preço atual de um ativo.

        Args:
            asset (str): Símbolo do ativo.
            current_prices (dict): Preços atuais.

        Returns:
            Optional[Decimal]: Preço atual ou None se não encontrado.

        """
        # Procura por pares que terminam com o ativo
        for symbol, price_data in current_prices.items():
            if symbol.endswith(asset):
                return Decimal(price_data.get("bidPrice", "0"))

        return None

    def reset_daily_pnl(self):
        """Reseta o PnL diário (chamado no início de cada dia)."""
        self.daily_pnl = Decimal(0)
        logging.info("PnL diário resetado.")

    def get_risk_metrics(self) -> dict:
        """Retorna métricas de risco atuais.

        Returns:
            dict: Métricas de risco.

        """
        return {
            "daily_pnl": float(self.daily_pnl),
            "open_positions": len(self.open_positions),
            "total_positions": len(self.position_history),
            "win_rate": float(self._calculate_historical_win_rate()),
            "avg_win": float(self._calculate_average_win()),
            "avg_loss": float(self._calculate_average_loss()),
            "max_daily_loss": float(self.max_daily_loss),
            "max_portfolio_risk": float(self.max_portfolio_risk),
        }

    def _optimize_portfolio_allocation_hydra(
        self,
        return_paths: list[PathAnalysis],
        forward_paths: list[PathAnalysis],
        total_capital: Decimal,
    ) -> PortfolioAllocation:
        """HYDRA 2.0: Otimização avançada de portfólio considerando caminhos de retorno e avanço.

        Args:
            return_paths: Lista de análises de caminhos que retornam ao ativo inicial
            forward_paths: Lista de análises de caminhos que terminam em outros ativos
            total_capital: Capital total disponível

        Returns:
            PortfolioAllocation: Alocação otimizada do portfólio

        """
        all_paths = return_paths + forward_paths

        if not all_paths:
            return PortfolioAllocation(
                [],
                Decimal(0),
                Decimal(0),
                Decimal(0),
                "no_paths",
            )

        # HYDRA 2.0: Estratégia de múltiplas cabeças
        if len(all_paths) == 1:
            # Caminho único: aloca 100% do capital
            path = all_paths[0]
            allocation = {
                "path": path.path_info["path"],
                "allocation_percentage": Decimal("1.0"),
                "investment_amount": total_capital,
                "expected_profit": path.expected_profit,
                "risk_score": path.risk_score,
                "strategy_type": "single_path",
            }
            return PortfolioAllocation(
                [allocation],
                path.expected_profit,
                path.risk_score,
                Decimal(0),
                "single_path",
            )

        # Múltiplos caminhos: estratégia Hydra de múltiplas cabeças
        # Prioriza caminhos de avanço (pathfinding avançado) sobre retornos
        sorted_paths = sorted(
            all_paths,
            key=lambda x: (
                not x.path_info.get(
                    "returns_to_start",
                    True,
                ),  # Caminhos de avanço primeiro
                x.expected_profit,  # Depois por lucro esperado
                -x.risk_score,  # Depois por menor risco
            ),
            reverse=True,
        )

        # Seleciona os melhores caminhos (máximo 3 para diversificação)
        selected_paths = sorted_paths[:3]

        # Calcula alocação baseada no Sharpe ratio e correlação
        allocations = []
        total_expected_profit = Decimal(0)
        total_risk = Decimal(0)

        for _i, path in enumerate(selected_paths):
            # Alocação baseada no Sharpe ratio
            if path.sharpe_ratio > self.min_sharpe_ratio:
                # Aloca mais capital para caminhos com melhor Sharpe ratio
                allocation_pct = min(Decimal("0.6"), path.sharpe_ratio / Decimal(2))
            else:
                allocation_pct = Decimal("0.2")  # Alocação mínima

            # Ajusta para caminhos de avanço (pathfinding avançado)
            if not path.path_info.get("returns_to_start", True):
                allocation_pct *= Decimal("1.5")  # 50% mais capital para pathfinding

            investment_amount = total_capital * allocation_pct

            allocation = {
                "path": path.path_info["path"],
                "allocation_percentage": allocation_pct,
                "investment_amount": investment_amount,
                "expected_profit": path.expected_profit * allocation_pct,
                "risk_score": path.risk_score,
                "strategy_type": "hydra_multi_head",
                "returns_to_start": path.path_info.get("returns_to_start", True),
            }

            allocations.append(allocation)
            total_expected_profit += allocation["expected_profit"]
            total_risk = max(total_risk, path.risk_score)

        # Calcula score de diversificação
        diversification_score = self._calculate_diversification_score(selected_paths)

        strategy_name = f"hydra_{len(selected_paths)}_heads"
        if any(not p.path_info.get("returns_to_start", True) for p in selected_paths):
            strategy_name += "_pathfinding"

        logging.info(
            f"🚀 HYDRA 2.0: Estratégia {strategy_name} com {len(selected_paths)} caminhos",
        )
        logging.info(
            f"   Caminhos de retorno: {sum(1 for p in selected_paths if p.path_info.get('returns_to_start', True))}",
        )
        logging.info(
            f"   Caminhos de avanço: {sum(1 for p in selected_paths if not p.path_info.get('returns_to_start', True))}",
        )

        return PortfolioAllocation(
            allocations,
            total_expected_profit,
            total_risk,
            diversification_score,
            strategy_name,
        )
