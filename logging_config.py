"""Módulo de configuração centralizada de logging para o Sistema Hydra Crypto.
Implementa logging estruturado com rotação de arquivos e diferentes níveis.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class HydraLogger:
    """Sistema de logging centralizado para o Hydra Crypto Bot.
    Implementa logging estruturado com rotação e diferentes handlers.
    """

    def __init__(self, log_dir: str = "logs", log_level: str = "INFO") -> None:
        """Inicializa o sistema de logging.

        Args:
            log_dir: Diretório para armazenar os logs
            log_level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())

        # Cria diretório de logs se não existir
        self.log_dir.mkdir(exist_ok=True)

        # Configura o logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configura o sistema de logging."""
        # Remove handlers existentes
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Configura o logger raiz
        logging.root.setLevel(self.log_level)

        # Formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
        )

        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
        )

        json_formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
        )

        # Console Handler (INFO e acima)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logging.root.addHandler(console_handler)

        # File Handler - Geral (rotação diária)
        general_handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / "hydra_crypto.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        general_handler.setLevel(logging.DEBUG)
        general_handler.setFormatter(detailed_formatter)
        logging.root.addHandler(general_handler)

        # File Handler - Erros (rotação diária)
        error_handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / "errors.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logging.root.addHandler(error_handler)

        # File Handler - Trading (rotação por hora)
        trading_handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / "trading.log",
            when="H",
            interval=1,
            backupCount=168,  # 7 dias
            encoding="utf-8",
        )
        trading_handler.setLevel(logging.INFO)
        trading_handler.setFormatter(json_formatter)
        logging.root.addHandler(trading_handler)

        # File Handler - Performance (rotação diária)
        performance_handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / "performance.log",
            when="midnight",
            interval=1,
            backupCount=90,  # 3 meses
            encoding="utf-8",
        )
        performance_handler.setLevel(logging.INFO)
        performance_handler.setFormatter(json_formatter)
        logging.root.addHandler(performance_handler)

        # Filtros específicos
        trading_filter = TradingFilter()
        trading_handler.addFilter(trading_filter)

        performance_filter = PerformanceFilter()
        performance_handler.addFilter(performance_filter)

    def get_logger(self, name: str) -> logging.Logger:
        """Obtém um logger configurado para um módulo específico.

        Args:
            name: Nome do módulo/logger

        Returns:
            Logger configurado

        """
        return logging.getLogger(name)

    def log_trade(self, trade_data: dict[str, Any]) -> None:
        """Loga informações de uma operação de trading.

        Args:
            trade_data: Dados da operação

        """
        logger = logging.getLogger("trading")
        logger.info(f"TRADE: {trade_data}")

    def log_performance(self, performance_data: dict[str, Any]) -> None:
        """Loga métricas de performance.

        Args:
            performance_data: Dados de performance

        """
        logger = logging.getLogger("performance")
        logger.info(f"PERFORMANCE: {performance_data}")

    def log_error(self, error: Exception, context: str = "") -> None:
        """Loga erros com contexto.

        Args:
            error: Exceção ocorrida
            context: Contexto adicional

        """
        logger = logging.getLogger("errors")
        logger.error(f"ERROR in {context}: {error}", exc_info=True)

    def cleanup_old_logs(self, days: int = 30) -> None:
        """Remove logs antigos.

        Args:
            days: Número de dias para manter

        """
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

        for log_file in self.log_dir.glob("*.log.*"):
            if log_file.stat().st_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    logging.info(f"Removido log antigo: {log_file}")
                except Exception as e:
                    logging.warning(f"Erro ao remover log antigo {log_file}: {e}")

    def shutdown(self) -> None:
        """Fecha todos os handlers de logging."""
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)


class TradingFilter(logging.Filter):
    """Filtro para logs de trading."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "TRADE:" in record.getMessage() or "trading" in record.name.lower()


class PerformanceFilter(logging.Filter):
    """Filtro para logs de performance."""

    def filter(self, record: logging.LogRecord) -> bool:
        return (
            "PERFORMANCE:" in record.getMessage()
            or "performance" in record.name.lower()
        )


# Instância global do logger
_hydra_logger: HydraLogger | None = None


def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> HydraLogger:
    """Configura o sistema de logging global.

    Args:
        log_dir: Diretório para logs
        log_level: Nível de logging

    Returns:
        Instância do HydraLogger

    """
    global _hydra_logger
    _hydra_logger = HydraLogger(log_dir, log_level)
    return _hydra_logger


def get_logger(name: str) -> logging.Logger:
    """Obtém um logger configurado.

    Args:
        name: Nome do logger

    Returns:
        Logger configurado

    """
    if (
        _hydra_logger is None
    ):  # pragma: no cover - inicialização indireta coberta em testes
        setup_logging()  # pragma: no cover
    return _hydra_logger.get_logger(name)


def log_trade(trade_data: dict[str, Any]) -> None:
    """Loga dados de trading."""
    if _hydra_logger is None:  # pragma: no cover
        setup_logging()  # pragma: no cover
    _hydra_logger.log_trade(trade_data)


def log_performance(performance_data: dict[str, Any]) -> None:
    """Loga dados de performance."""
    if _hydra_logger is None:  # pragma: no cover
        setup_logging()  # pragma: no cover
    _hydra_logger.log_performance(performance_data)


def log_error(error: Exception, context: str = "") -> None:
    """Loga erros."""
    if _hydra_logger is None:  # pragma: no cover
        setup_logging()  # pragma: no cover
    _hydra_logger.log_error(error, context)


# Configuração automática quando o módulo é importado
# Comentado para evitar problemas nos testes
# if _hydra_logger is None:  # pragma: no cover
#     setup_logging()  # pragma: no cover
