import logging
import time
from threading import Event, Thread

import psutil


class TradingPerformance:
    """Métricas de performance de trading."""

    def __init__(self) -> None:
        self.trades_per_second: int = 0
        self.success_rate: float = 0.0
        self.total_profit: float = 0.0


class NetworkPerformance:
    """Métricas de performance de rede."""

    def __init__(self) -> None:
        self.api_latency: float = 0.0
        self.websocket_latency: float = 0.0


class PerformanceMonitor:
    """Monitora a performance do sistema e da rede."""

    def __init__(self) -> None:
        self.running: bool = False
        self._stop_event: Event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Inicia o monitoramento em um thread separado."""
        self.running = True
        self._thread = Thread(target=self._monitor_loop)
        self._thread.daemon = True
        self._thread.start()
        logging.info("Performance monitor iniciado.")

    def stop(self) -> None:
        """Para o monitoramento."""
        self.running = False
        if self._thread:
            self._stop_event.set()
            self._thread.join()
        logging.info("Performance monitor parado.")

    def _monitor_loop(self) -> None:
        """Loop principal de monitoramento."""
        while not self._stop_event.is_set():
            try:
                self.log_system_metrics()
            except Exception as e:
                logging.error(f"Erro no loop do monitor de performance: {e}", exc_info=True)
            time.sleep(60)  # Log a cada 60 segundos

    def log_system_metrics(self) -> None:
        """Loga as métricas de uso do sistema (CPU, memória)."""
        cpu_usage = psutil.cpu_percent()
        memory_info = psutil.virtual_memory()
        logging.info(
            f"Métricas do Sistema: CPU: {cpu_usage}%, Memória: {memory_info.percent}%",
        )
