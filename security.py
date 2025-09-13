"""Módulo de segurança para lidar com a assinatura de requisições."""

import hashlib
import hmac
from urllib.parse import urlencode


class Security:
    """Lida com a segurança das requisições, como a assinatura HMAC."""

    def __init__(self, secret: str):
        """Inicializa o módulo de segurança.

        Args:
            secret (str): O segredo da API para assinar as requisições.

        """
        if not secret or not isinstance(secret, str):
            raise ValueError("O segredo da API é inválido.")
        self.secret = secret.encode("utf-8")

    def get_signed_params(self, params: dict) -> dict:
        """Assina um dicionário de parâmetros e retorna os parâmetros com a assinatura.

        Args:
            params (dict): Os parâmetros a serem assinados.

        Returns:
            dict: Os parâmetros originais com a assinatura adicionada.

        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret,
            msg=query_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params
