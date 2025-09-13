import logging
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO


class TradingMetrics:
    """Métricas de trading para o dashboard."""

    def __init__(
        self,
        total_trades=0,
        successful_trades=0,
        failed_trades=0,
        total_profit=0.0,
        success_rate=0.0,
        avg_profit=0.0,
        active_tickers=0,
        market_volatility=0.0,
        market_volume=0.0,
    ):
        self.total_trades = total_trades
        self.successful_trades = successful_trades
        self.failed_trades = failed_trades
        self.total_profit = total_profit
        self.success_rate = success_rate
        self.avg_profit = avg_profit
        self.active_tickers = active_tickers
        self.last_update = None
        self.market_data = {}
        self.recent_paths = []
        self.market_volatility = market_volatility
        self.market_volume = market_volume


class Dashboard:
    """Dashboard para visualização de dados em tempo real."""

    def __init__(self, host="127.0.0.1", port=5000):
        self.app = Flask(__name__, template_folder='templates')
        self.socketio = SocketIO(self.app)
        self.host = host
        self.port = port
        self.metrics = TradingMetrics()
        self._configure_routes()

    def _configure_routes(self):
        """Configura as rotas da aplicação Flask."""

        @self.app.route("/")
        def index():
            return render_template("dashboard.html")

        @self.app.route("/metrics")
        def get_metrics():
            return jsonify(self.metrics.__dict__)

        # Endpoints compatíveis com o front-end
        @self.app.route("/api/metrics")
        def api_metrics():
            return jsonify(self.metrics.__dict__)

        @self.app.route("/api/status")
        def api_status():
            return jsonify(
                {
                    "status": "ok",
                    "total_trades": self.metrics.total_trades,
                    "successful_trades": self.metrics.successful_trades,
                    "failed_trades": self.metrics.failed_trades,
                    "total_profit": self.metrics.total_profit,
                },
            )

    def update_metrics(self, new_metrics: TradingMetrics):
        """Atualiza as métricas e emite para os clientes."""
        self.metrics = new_metrics
        self.socketio.emit("metrics_update", self.metrics.__dict__)

    def update_market_data(self, tickers: dict, profitable_paths: list = None):
        """Atualiza dados de mercado em tempo real."""
        import time

        logging.info(
            f"📊 Dashboard: Atualizando dados de mercado com {len(tickers)} tickers",
        )

        # Atualiza métricas básicas
        self.metrics.active_tickers = len(tickers)
        self.metrics.last_update = time.time()

        # Atualiza dados de mercado
        self.metrics.market_data = {
            "total_pairs": len(tickers),
            "sample_pairs": dict(
                list(tickers.items())[:10],
            ),  # Primeiros 10 pares como exemplo
        }

        # Atualiza caminhos lucrativos
        if profitable_paths:
            self.metrics.recent_paths = profitable_paths[:5]  # Últimos 5 caminhos
            logging.info(
                f"📊 Dashboard: Encontrados {len(profitable_paths)} caminhos lucrativos",
            )
        else:
            self.metrics.recent_paths = []

        # Prepara dados para envio
        update_data = {
            "active_tickers": self.metrics.active_tickers,
            "last_update": self.metrics.last_update,
            "market_data": self.metrics.market_data,
            "recent_paths": self.metrics.recent_paths,
            # Inclui todas as métricas de trading
            "total_trades": self.metrics.total_trades,
            "successful_trades": self.metrics.successful_trades,
            "failed_trades": self.metrics.failed_trades,
            "total_profit": self.metrics.total_profit,
        }

        # Unifica todos os dados em um único evento 'full_update'
        full_update_data = {**self.metrics.__dict__, **update_data}

        logging.info("📊 Dashboard: Enviando 'full_update' para clientes")
        self.socketio.emit("full_update", full_update_data)

    def run(self):
        """Executa o servidor do dashboard."""
        self.socketio.run(
            self.app,
            host=self.host,
            port=self.port,
            debug=False,
        )  # pragma: no cover

    def start(self):
        """Inicia o servidor do dashboard em um thread separado."""
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()
        logging.info(f"Dashboard iniciado em http://{self.host}:{self.port}")


def create_dashboard(enable_web=True, port=5000):
    """Cria e retorna uma instância do dashboard."""
    if enable_web:
        return Dashboard(port=port)
    return None
