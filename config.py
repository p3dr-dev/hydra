"""Módulo de configuração para gerenciar chaves de API e outros segredos."""

import os

from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()


class ConfigError(Exception):
    """Exceção para erros de configuração."""


class Config:
    """Gerencia a configuração do bot, carregando dados de variáveis de ambiente."""

    # URLs da API da Binance, conforme documentação
    # Usado pelo ApiClient para implementar failover e resiliência
    BINANCE_API_URLS = {
        "main": "https://api.binance.com",
        "alternatives": [
            "https://api1.binance.com",
            "https://api2.binance.com",
            "https://api3.binance.com",
            "https://api4.binance.com",
        ],
        "data": "https://data-api.binance.vision",
    }

    def __init__(self, api_key: str, api_secret: str):
        """Inicializa a configuração.

        Args:
            api_key (str): A chave da API da Binance.
            api_secret (str): O segredo da API da Binance.

        """
        if not api_key or not isinstance(api_key, str):
            raise ConfigError("A chave da API (api_key) é inválida.")
        if not api_secret or not isinstance(api_secret, str):
            raise ConfigError("O segredo da API (api_secret) é inválido.")

        self.api_key = api_key
        self.api_secret = api_secret
        self.base_urls = self.BINANCE_API_URLS

    @classmethod
    def from_env(cls):
        """Cria uma instância de Config a partir de variáveis de ambiente.

        Raises:
            ConfigError: Se as variáveis de ambiente não estiverem definidas.

        Returns:
            Config: Uma instância da classe Config.

        """
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")

        if not api_key:
            raise ConfigError(
                "A variável de ambiente BINANCE_API_KEY não está definida.",
            )
        if not api_secret:
            raise ConfigError(
                "A variável de ambiente BINANCE_API_SECRET não está definida.",
            )

        return cls(api_key=api_key, api_secret=api_secret)


# Exemplo de como usar:
# try:
#     config = Config.from_env()
#     print("Configuração carregada com sucesso.")
#     # print(f"API Key: {config.api_key}")
# except ConfigError as e:
#     print(f"Erro de configuração: {e}")
#     # Lógica para lidar com a ausência de configuração
#     # Por exemplo, solicitar ao usuário ou encerrar o programa.
#     exit(1)
