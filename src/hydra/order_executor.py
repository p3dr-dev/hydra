"""Módulo de execução de ordens para o bot de trading.
Implementa execução de ordens individuais e caminhos completos de arbitragem.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal

from .api_client import ApiClient
from .data_analyzer import DataAnalyzer
from .resilience import resilient, retry
from .risk_manager import RiskManager

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Resultado da execução de uma ordem."""

    success: bool
    symbol: str
    side: str
    quantity: Decimal
    order_id: str | None  # Adicionado para rastreamento
    executed_price: Decimal | None
    commission: Decimal | None
    error_message: str | None
    execution_time: float


@dataclass
class PathExecutionResult:
    """Resultado da execução de um caminho completo."""

    path: list[str]
    success: bool
    initial_amount: Decimal
    final_amount: Decimal
    profit_loss: Decimal
    execution_results: list[ExecutionResult]
    total_commission: Decimal
    execution_time: float


class OrderExecutor:
    """Executor de ordens para o bot de trading.
    Responsável por executar ordens individuais e caminhos completos de arbitragem.
    """

    def __init__(
        self,
        api_client: ApiClient,
        data_analyzer: DataAnalyzer,
        risk_manager: RiskManager,
    ):
        """Inicializa o executor de ordens.

        Args:
            api_client (ApiClient): Cliente da API da Binance.
            data_analyzer (DataAnalyzer): Analisador de dados de mercado.
            risk_manager (RiskManager): Gerenciador de risco.

        """
        self.api_client = api_client
        self.data_analyzer = data_analyzer
        self.risk_manager = risk_manager
        self.dry_run = False
        self.execution_history = []

    def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> ExecutionResult:
        """Executa uma ordem de negociação.

        Args:
            symbol (str): Símbolo da negociação (ex: 'BTCUSDT').
            side (str): Lado da ordem ('BUY' ou 'SELL').
            quantity (Decimal): Quantidade a ser negociada.

        Returns:
            ExecutionResult: Resultado da execução da ordem.

        """
        import time

        start_time = time.time()

        try:
            # Modo LIVE - execução real na Binance
            logging.info(f"[LIVE] Executando ordem: {side} {quantity:.8f} {symbol}")
            return self._execute_live_trade(symbol, side, quantity, start_time)

        except Exception as e:
            execution_time = time.time() - start_time
            logging.exception(f"Erro na execução da ordem {symbol} {side}: {e!s}")
            return ExecutionResult(
                success=False,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_id=None,
                executed_price=None,
                commission=None,
                error_message=str(e),
                execution_time=execution_time,
            )

    @resilient(circuit_name="live_trade", retry_name="critical_operations")
    def _execute_live_trade(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        start_time: float,
    ) -> ExecutionResult:
        """Executa uma ordem real na Binance.

        Args:
            symbol (str): Símbolo da negociação.
            side (str): Lado da ordem.
            quantity (Decimal): Quantidade.
            start_time (float): Tempo de início.

        Returns:
            ExecutionResult: Resultado da execução.

        """
        try:
            # Verifica se o símbolo está ativo
            if not self._is_symbol_active(symbol):
                raise ValueError(f"Símbolo {symbol} não está ativo para negociação")

            # Obtém informações do símbolo
            symbol_info = self._get_symbol_info(symbol)
            if not symbol_info:
                raise ValueError(
                    f"Não foi possível obter informações do símbolo {symbol}",
                )

            # Ajusta quantidade para os filtros
            adjusted_quantity = self.risk_manager.adjust_quantity_to_filters(
                symbol,
                quantity,
            )
            if adjusted_quantity <= 0:
                raise ValueError(
                    f"Quantidade ajustada para {symbol} é zero ou inválida",
                )

            # Cria a ordem na Binance
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",  # Ordem de mercado para execução imediata
                "quantity": str(adjusted_quantity),
            }

            # Adiciona timestamp para evitar replay attacks
            order_params["timestamp"] = int(time.time() * 1000)

            # Valida a ordem com um teste antes de executar
            logging.info(f"[TEST] Validando ordem: {side} {adjusted_quantity} {symbol}")
            self.api_client.test_place_order(order_params)
            logging.info("[TEST] Validação da ordem bem-sucedida.")

            # Executa a ordem
            response = self.api_client.place_order(order_params)

            if not response or "orderId" not in response:
                raise ValueError("Resposta inválida da API da Binance")

            # Obtém detalhes da ordem executada
            order_details = self._get_order_details(symbol, response["orderId"])

            if not order_details:
                raise ValueError("Não foi possível obter detalhes da ordem executada")

            # Calcula comissão real
            commission = self._calculate_real_commission(
                order_details.get('fills', []),
                symbol_info.get('quoteAsset')
            )

            return ExecutionResult(
                success=True,
                symbol=symbol,
                side=side,
                quantity=Decimal(str(order_details.get("executedQty", "0"))),
                executed_price=Decimal(str(order_details.get("price", "0"))),
                commission=commission,
                error_message=None,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            logging.exception(f"Erro na execução LIVE da ordem {symbol}: {e!s}")
            return ExecutionResult(
                success=False,
                symbol=symbol,
                side=side,
                quantity=quantity,
                executed_price=None,
                commission=None,
                error_message=str(e),
                execution_time=time.time() - start_time,
            )

    def execute_single_path(
        self,
        instruction: dict,
        tickers: dict,
        order_books: dict,
    ) -> PathExecutionResult:
        """Executa um caminho completo de arbitragem.

        Args:
            instruction (dict): Instrução de negociação contendo path_info e investment_size.
            tickers (dict): Estado atual dos tickers para os cálculos.
            order_books (dict): Cache de order books em tempo real.

        Returns:
            PathExecutionResult: Resultado da execução do caminho.

        """
        import time

        start_time = time.time()

        path_info = instruction["path_info"]
        path = path_info["path"]
        initial_amount = instruction["investment_size"]
        current_amount = initial_amount

        logging.info(
            f"--- Iniciando execução da oportunidade: {path} com {initial_amount:.8f} {path[0]} ---",
        )

        execution_results = []
        total_commission = Decimal(0)

        for i in range(len(path) - 1):
            asset_from = path[i]
            asset_to = path[i + 1]

            symbol, side = self.data_analyzer.get_symbol_and_side(
                tickers,
                asset_from,
                asset_to,
            )
            if not symbol:
                error_msg = f"Não foi possível determinar o símbolo para {asset_from}->{asset_to}"
                logging.error(f"{error_msg}. Abortando caminho.")
                return PathExecutionResult(
                    path=path,
                    success=False,
                    initial_amount=initial_amount,
                    final_amount=current_amount,
                    profit_loss=current_amount - initial_amount,
                    execution_results=execution_results,
                    total_commission=total_commission,
                    execution_time=time.time() - start_time,
                )

            # Ajusta a quantidade para os filtros do símbolo
            adjusted_quantity = self.risk_manager.adjust_quantity_to_filters(
                symbol,
                current_amount,
            )
            if adjusted_quantity <= 0:
                error_msg = f"Quantidade ajustada para {symbol} é zero"
                logging.warning(f"{error_msg}. Interrompendo o caminho.")
                return PathExecutionResult(
                    path=path,
                    success=False,
                    initial_amount=initial_amount,
                    final_amount=current_amount,
                    profit_loss=current_amount - initial_amount,
                    execution_results=execution_results,
                    total_commission=total_commission,
                    execution_time=time.time() - start_time,
                )

            # Executa a ordem
            result = self.execute_trade(symbol, side, adjusted_quantity)
            execution_results.append(result)

            if not result.success:
                logging.error(
                    f"Falha ao executar o passo {asset_from} -> {asset_to}. Erro: {result.error_message}",
                )
                return PathExecutionResult(
                    path=path,
                    success=False,
                    initial_amount=initial_amount,
                    final_amount=current_amount,
                    profit_loss=current_amount - initial_amount,
                    execution_results=execution_results,
                    total_commission=total_commission,
                    execution_time=time.time() - start_time,
                )

            # --- INÍCIO DA CORREÇÃO CRÍTICA ---
            # ATUALIZA O MONTANTE COM BASE NO RESULTADO REAL, NÃO EM NOVA SIMULAÇÃO
            
            # Obtém os detalhes da ordem real que foi executada
            order_details = self._get_order_details(symbol, result.order_id)
            if not order_details or 'fills' not in order_details or not order_details['fills']:
                 logging.error(f"Não foi possível obter os 'fills' da ordem {result.order_id} para {symbol}. Abortando.")
                 # Lógica de falha...
                 return PathExecutionResult(
                    path=path,
                    success=False,
                    initial_amount=initial_amount,
                    final_amount=current_amount,
                    profit_loss=current_amount - initial_amount,
                    execution_results=execution_results,
                    total_commission=total_commission,
                    execution_time=time.time() - start_time,
                )
            
            # Ordens de mercado podem ter múltiplos 'fills'. Somamos todos.
            total_qty_received = Decimal('0')
            total_commission_in_asset = Decimal('0')
            commission_asset = ''
            
            if side == 'BUY':
                # Se compramos, o novo montante é a quantidade executada menos a comissão
                for fill in order_details['fills']:
                    total_qty_received += Decimal(fill['qty'])
                    total_commission_in_asset += Decimal(fill['commission'])
                    commission_asset = fill['commissionAsset']
                # Se a comissão foi paga no próprio ativo, subtraia
                if commission_asset == asset_to:
                    current_amount = total_qty_received - total_commission_in_asset
                else:
                    current_amount = total_qty_received

            else: # side == 'SELL'
                # Se vendemos, o novo montante é o total em 'quote' recebido
                for fill in order_details['fills']:
                    total_qty_received += Decimal(fill['quoteQty'])
                    total_commission_in_asset += Decimal(fill['commission'])
                    commission_asset = fill['commissionAsset']
                # Se a comissão foi paga no ativo 'quote' recebido, subtraia
                if commission_asset == asset_to:
                    current_amount = total_qty_received - total_commission_in_asset
                else:
                    current_amount = total_qty_received

            if current_amount <= 0:
                logging.warning("A quantidade REAL resultante da negociação foi zero. Interrompendo.")
                # Lógica de falha...
                return PathExecutionResult(
                    path=path,
                    success=False,
                    initial_amount=initial_amount,
                    final_amount=current_amount,
                    profit_loss=current_amount - initial_amount,
                    execution_results=execution_results,
                    total_commission=total_commission,
                    execution_time=time.time() - start_time,
                )

            logging.info(f"Execução real {symbol}: {adjusted_quantity:.8f} {asset_from} -> {current_amount:.8f} {asset_to}")
            # --- FIM DA CORREÇÃO CRÍTICA ---

        profit_loss = current_amount - initial_amount
        success = profit_loss > 0

        logging.info(
            f"--- Execução da oportunidade {path} concluída. Lucro: {profit_loss:.8f} {path[0]} ---",
        )

        return PathExecutionResult(
            path=path,
            success=success,
            initial_amount=initial_amount,
            final_amount=current_amount,
            profit_loss=profit_loss,
            execution_results=execution_results,
            total_commission=total_commission,
            execution_time=time.time() - start_time,
        )

    def execute_instructions_parallel(
        self,
        instructions: list[dict],
        tickers: dict,
        order_books: dict,
    ) -> list[PathExecutionResult]:
        """Executa múltiplas instruções em paralelo (estratégia Hydra 2.0).

        Args:
            instructions (list[dict]): A lista de instruções de negociação.
            tickers (dict): O estado atual dos tickers para os cálculos.
            order_books (dict): Cache de order books em tempo real.

        Returns:
            List[PathExecutionResult]: Lista de resultados de execução.

        """
        if not instructions:
            logging.info("Nenhuma instrução para executar.")
            return []

        logging.info(f"Iniciando execução paralela de {len(instructions)} caminhos...")

        results = []
        with ThreadPoolExecutor(max_workers=min(len(instructions), 5)) as executor:
            # Submete todas as tarefas
            future_to_instruction = {
                executor.submit(
                    self.execute_single_path,
                    instruction,
                    tickers,
                    order_books,
                ): instruction
                for instruction in instructions
            }

            # Coleta os resultados conforme são concluídos
            for future in as_completed(future_to_instruction):
                instruction = future_to_instruction[future]
                try:
                    result = future.result()
                    results.append(result)
                    logging.info(
                        f"Caminho {result.path} concluído com {'sucesso' if result.success else 'falha'}",
                    )
                except Exception as e:
                    logging.exception(
                        f"Erro na execução do caminho {instruction.get('path_info', {}).get('path', 'unknown')}: {e}",
                    )
                    # Cria um resultado de erro
                    error_result = PathExecutionResult(
                        path=instruction.get("path_info", {}).get("path", []),
                        success=False,
                        initial_amount=instruction.get("investment_size", Decimal(0)),
                        final_amount=instruction.get("investment_size", Decimal(0)),
                        profit_loss=Decimal(0),
                        execution_results=[],
                        total_commission=Decimal(0),
                        execution_time=0.0,
                    )
                    results.append(error_result)

        logging.info(
            f"Execução paralela concluída. {len(results)} caminhos processados.",
        )
        return results

    def execute_instructions(
        self,
        instructions: list[dict],
        tickers: dict,
        order_books: dict,
    ):
        """Executa as instruções de negociação usando a estratégia Hydra 2.0.

        Args:
            instructions (list[dict]): Lista de instruções de negociação.
            tickers (dict): Estado atual dos tickers.
            order_books (dict): Cache de order books em tempo real.

        Returns:
            List[PathExecutionResult]: Resultados da execução.

        """
        if not instructions:
            logging.info("Nenhuma instrução para executar.")
            return []

        # Executa em paralelo para maximizar oportunidades
        results = self.execute_instructions_parallel(instructions, tickers, order_books)

        # Adiciona à história de execução
        self.execution_history.extend(results)

        # Persiste o regime operacional para cada resultado
        for result in results:
            current_regime = self.risk_manager.get_current_regime()
            predicted_profit = float(result.profit_loss) / float(result.initial_amount) if result.initial_amount > 0 else 0.0
            self._persist_execution_result(result, predicted_profit, current_regime)

        # Log dos resultados
        successful_paths = [r for r in results if r.success]
        failed_paths = [r for r in results if not r.success]

        logging.info(
            f"Execução concluída: {len(successful_paths)} caminhos bem-sucedidos, {len(failed_paths)} falharam",
        )

        if successful_paths:
            total_profit = sum(r.profit_loss for r in successful_paths)
            logging.info(f"Lucro total dos caminhos bem-sucedidos: {total_profit:.8f}")

        return results

    def _persist_execution_result(self, result: PathExecutionResult, predicted_profit_percent: float, operating_regime: str):
        """Persiste o resultado da execução no banco de dados."""
        try:
            import sqlite3
            conn = sqlite3.connect('hydra_memory.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    timestamp TEXT,
                    path TEXT,
                    success INTEGER,
                    profit_loss REAL,
                    initial_amount REAL,
                    final_amount REAL,
                    execution_time REAL,
                    total_commission REAL,
                    predicted_profit_percent REAL,
                    operating_regime TEXT
                )
            ''')
            cursor.execute(
                "INSERT INTO trade_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    str(result.path),
                    1 if result.success else 0,
                    float(result.profit_loss),
                    float(result.initial_amount),
                    float(result.final_amount),
                    result.execution_time,
                    float(result.total_commission),
                    predicted_profit_percent,
                    operating_regime
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logging.exception(f"Erro ao persistir resultado: {e}")

    def get_execution_statistics(self) -> dict:
        """Retorna estatísticas de execução.

        Returns:
            dict: Estatísticas de execução.

        """
        if not self.execution_history:
            return {
                "total_executions": 0,
                "total_paths": 0,
                "successful_paths": 0,
                "failed_paths": 0,
                "total_profit": 0,
                "total_commission": 0,
                "success_rate": 0,
            }

        total_paths = len(self.execution_history)
        successful_paths = len([r for r in self.execution_history if r.success])
        failed_paths = total_paths - successful_paths
        total_profit = sum(r.profit_loss for r in self.execution_history if r.success)
        total_commission = sum(r.total_commission for r in self.execution_history)
        success_rate = (successful_paths / total_paths) * 100 if total_paths > 0 else 0

        return {
            "total_executions": total_paths,
            "total_paths": total_paths,
            "successful_paths": successful_paths,
            "failed_paths": failed_paths,
            "total_profit": float(total_profit),
            "total_commission": float(total_commission),
            "success_rate": success_rate,
        }

    @retry(max_retries=2, base_delay=0.5)
    def _is_symbol_active(self, symbol: str) -> bool:
        """Verifica se um símbolo está ativo para negociação.

        Args:
            symbol (str): Símbolo a ser verificado.

        Returns:
            bool: True se o símbolo está ativo.

        """
        try:
            exchange_info = self.api_client.get_exchange_info()
            symbols = exchange_info.get("symbols", [])

            for sym in symbols:
                if sym["symbol"] == symbol:
                    return sym["status"] == "TRADING"

            return False
        except Exception as e:
            logging.exception(f"Erro ao verificar se símbolo {symbol} está ativo: {e}")
            return False

    @retry(max_retries=2, base_delay=0.5)
    def _get_symbol_info(self, symbol: str) -> dict:
        """Obtém informações detalhadas de um símbolo.

        Args:
            symbol (str): Símbolo para obter informações.

        Returns:
            dict: Informações do símbolo ou None se não encontrado.

        """
        try:
            exchange_info = self.api_client.get_exchange_info()
            symbols = exchange_info.get("symbols", [])

            for sym in symbols:
                if sym["symbol"] == symbol:
                    return sym

            return None
        except Exception as e:
            logging.exception(f"Erro ao obter informações do símbolo {symbol}: {e}")
            return None

    def _get_order_details(self, symbol: str, order_id: str) -> dict:
        """Obtém detalhes de uma ordem executada.

        Args:
            symbol (str): Símbolo da ordem.
            order_id (str): ID da ordem.

        Returns:
            dict: Detalhes da ordem ou None se não encontrada.

        """
        try:
            return self.api_client.get_order(symbol, order_id)
        except Exception as e:
            logging.exception(f"Erro ao obter detalhes da ordem {order_id}: {e}")
            return None

    def _calculate_real_commission(self, fills: list[dict], quote_asset: str) -> Decimal:
        """
        Calcula a comissão real de uma ordem a partir dos dados de 'fills', convertendo para o 'quote asset' do par.
        """
        total_commission_in_quote = Decimal('0')
        if not fills:
            return total_commission_in_quote

        for fill in fills:
            commission = Decimal(fill['commission'])
            commission_asset = fill['commissionAsset']
            price = Decimal(fill['price']) # Preço da transação

            if commission_asset == quote_asset:
                total_commission_in_quote += commission
            elif commission_asset == fill.get('baseAsset'): # Comissão paga no 'base asset'
                # Converte a comissão do base asset para o quote asset usando o preço da transação
                total_commission_in_quote += commission * price
            else:
                # Caso raro: comissão em um terceiro ativo (ex: BNB)
                # Aqui, uma chamada de API ainda seria necessária, mas é uma exceção.
                # Por simplicidade e eficiência, podemos logar um aviso por enquanto.
                logging.warning(f"Cálculo de comissão para ativo terceiro ({commission_asset}) não implementado. Usando valor bruto.")
                # Tenta converter para USDT como fallback
                usdt_price = self._get_asset_price_in_usdt(commission_asset)
                if usdt_price:
                    total_commission_in_quote += commission * usdt_price
        
        return total_commission_in_quote

    def _get_asset_price_in_usdt(self, asset: str) -> Decimal | None:
        """Obtém o preço de um ativo em USDT.

        Args:
            asset (str): Símbolo do ativo.

        Returns:
            Optional[Decimal]: Preço em USDT ou None se não encontrado.

        """
        try:
            if asset == "USDT":
                return Decimal("1.0")

            symbol = f"{asset}USDT"
            ticker = self.api_client.get_ticker_price(symbol)

            if ticker and "price" in ticker:
                return Decimal(str(ticker["price"]))

            return None
        except Exception as e:
            logging.exception(f"Erro ao obter preço de {asset} em USDT: {e}")
            return None

    def get_account_balance(self) -> dict:
        """Obtém o saldo da conta.

        Returns:
            dict: Saldos dos ativos.

        """
        try:
            account_info = self.api_client.get_account_info()
            balances = account_info.get("balances", [])

            # Filtra apenas ativos com saldo > 0
            non_zero_balances = {}
            for balance in balances:
                free = Decimal(str(balance.get("free", "0")))
                locked = Decimal(str(balance.get("locked", "0")))
                total = free + locked

                if total > 0:
                    non_zero_balances[balance["asset"]] = {
                        "free": float(free),
                        "locked": float(locked),
                        "total": float(total),
                    }

            return non_zero_balances
        except Exception as e:
            logging.exception(f"Erro ao obter saldo da conta: {e}")
            return {}

    def get_open_orders(self, symbol: str = None) -> list:
        """Obtém ordens abertas.

        Args:
            symbol (str, optional): Símbolo específico. Se None, retorna todas.

        Returns:
            list: Lista de ordens abertas.

        """
        try:
            return self.api_client.get_open_orders(symbol)
        except Exception as e:
            logging.exception(f"Erro ao obter ordens abertas: {e}")
            return []

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancela uma ordem.

        Args:
            symbol (str): Símbolo da ordem.
            order_id (str): ID da ordem.

        Returns:
            bool: True se cancelada com sucesso.

        """
        try:
            result = self.api_client.cancel_order(symbol, order_id)
            return result is not None
        except Exception as e:
            logging.exception(f"Erro ao cancelar ordem {order_id}: {e}")
            return False

    def get_trade_history(self, symbol: str = None, limit: int = 1000) -> list:
        """Obtém histórico de trades.

        Args:
            symbol (str, optional): Símbolo específico. Se None, busca o histórico completo.
            limit (int): Número máximo de trades por símbolo.

        Returns:
            list: Lista de trades.

        """
        try:
            if symbol:
                # Busca para um símbolo específico
                return self.api_client.get_my_trades(symbol, limit)
            # Busca o histórico completo para todos os símbolos relevantes
            return self._fetch_full_history(limit)
        except Exception as e:
            logging.exception(f"Erro ao obter histórico de trades: {e}")
            return []

    def _fetch_full_history(self, limit_per_symbol: int) -> list:
        """Busca o histórico de trades para todos os símbolos relevantes da conta."""
        logging.info("Iniciando busca completa do histórico de trades...")
        all_trades = []
        try:
            # 1. Obter todos os símbolos existentes na exchange
            exchange_info = self.api_client.get_exchange_info()
            all_symbols = {s["symbol"] for s in exchange_info.get("symbols", [])}

            # 2. Obter todos os ativos que o usuário possui/possuía
            account_info = self.api_client.get_account_info()
            user_assets = {
                balance["asset"]
                for balance in account_info.get("balances", [])
                if Decimal(balance["free"]) > 0 or Decimal(balance["locked"]) > 0
            }

            # 3. Determinar os símbolos relevantes para o usuário
            relevant_symbols = {
                s for s in all_symbols if any(asset in s for asset in user_assets)
            }
            logging.info(
                f"Encontrados {len(relevant_symbols)} símbolos relevantes para consultar."
            )

            # 4. Buscar trades para cada símbolo em paralelo
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_symbol = {
                    executor.submit(
                        self.api_client.get_my_trades,
                        s,
                        limit_per_symbol,
                    ): s
                    for s in relevant_symbols
                }
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        trades = future.result()
                        if trades:
                            all_trades.extend(trades)
                            logging.info(
                                f"... {len(trades)} trades encontrados para {symbol}"
                            )
                    except Exception as exc:
                        logging.exception(f"Erro ao buscar trades para {symbol}: {exc}")

            # 5. Ordenar todos os trades por tempo
            all_trades.sort(key=lambda x: x["time"], reverse=True)
            logging.info(
                f"Busca completa do histórico concluída. Total de {len(all_trades)} trades encontrados."
            )
            return all_trades

        except Exception as e:
            logging.exception(f"Erro geral ao buscar histórico completo: {e}")
            return all_trades  # Retorna o que foi possível obter
