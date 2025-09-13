"""Módulo de resiliência para tratamento robusto de erros e falhas de rede.
Implementa circuit breaker, retry logic e fallback strategies.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

from requests.exceptions import ConnectionError, RequestException, Timeout


class CircuitState(Enum):
    """Estados do circuit breaker."""

    CLOSED = "CLOSED"  # Funcionando normalmente
    OPEN = "OPEN"  # Falhas detectadas, bloqueando requisições
    HALF_OPEN = "HALF_OPEN"  # Testando se o serviço se recuperou


@dataclass
class CircuitBreakerConfig:
    """Configuração do circuit breaker."""

    failure_threshold: int = 5  # Número de falhas para abrir o circuito
    recovery_timeout: int = 60  # Tempo em segundos para tentar recuperação
    expected_exception: type = Exception  # Tipo de exceção que indica falha


@dataclass
class RetryConfig:
    """Configuração do sistema de retry."""

    max_retries: int = 3  # Número máximo de tentativas
    base_delay: float = 1.0  # Delay base em segundos
    max_delay: float = 60.0  # Delay máximo em segundos
    exponential_backoff: bool = True  # Usar backoff exponencial


class CircuitBreaker:
    """Implementação do padrão Circuit Breaker para proteção contra falhas."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        """Inicializa o circuit breaker.

        Args:
            name (str): Nome do circuit breaker para identificação.
            config (CircuitBreakerConfig): Configuração do circuit breaker.

        """
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executa uma função com proteção do circuit breaker.

        Args:
            func (Callable): Função a ser executada.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Returns:
            Any: Resultado da função.

        Raises:
            Exception: Se o circuit breaker estiver aberto ou a função falhar.

        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logging.info(f"Circuit breaker {self.name} mudou para HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} está OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuit breaker."""
        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    def _on_success(self):
        """Chamado quando uma operação é bem-sucedida."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:  # Precisa de 2 sucessos para fechar
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logging.info(f"Circuit breaker {self.name} mudou para CLOSED")

    def _on_failure(self):
        """Chamado quando uma operação falha."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logging.warning(f"Circuit breaker {self.name} voltou para OPEN após falha")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logging.error(
                f"Circuit breaker {self.name} mudou para OPEN após {self.failure_count} falhas",
            )

    def get_status(self) -> dict[str, Any]:
        """Retorna o status atual do circuit breaker."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
        }


class RetryHandler:
    """Sistema de retry com backoff exponencial."""

    def __init__(self, config: RetryConfig):
        """Inicializa o retry handler.

        Args:
            config (RetryConfig): Configuração do retry.

        """
        self.config = config

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executa uma função com retry automático.

        Args:
            func (Callable): Função a ser executada.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Returns:
            Any: Resultado da função.

        Raises:
            Exception: Se todas as tentativas falharem.

        """
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (RequestException, Timeout, ConnectionError) as e:
                if attempt == self.config.max_retries:
                    logging.exception(
                        f"Todas as {self.config.max_retries + 1} tentativas falharam: {e}",
                    )
                    raise e

                delay = self._calculate_delay(attempt)
                logging.warning(
                    f"Tentativa {attempt + 1} falhou: {e}. Tentando novamente em {delay:.2f}s",
                )
                time.sleep(delay)

    def _calculate_delay(self, attempt: int) -> float:
        """Calcula o delay para a próxima tentativa."""
        if self.config.exponential_backoff:
            delay = self.config.base_delay * (2**attempt)
        else:
            delay = self.config.base_delay * (attempt + 1)

        return min(delay, self.config.max_delay)


class ResilienceManager:
    """Gerenciador central de resiliência que coordena circuit breakers e retry logic."""

    def __init__(self):
        """Inicializa o gerenciador de resiliência."""
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.retry_handlers: dict[str, RetryHandler] = {}

        # Configurações padrão
        self.default_circuit_config = CircuitBreakerConfig()
        self.default_retry_config = RetryConfig()

    def get_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Obtém ou cria um circuit breaker.

        Args:
            name (str): Nome do circuit breaker.
            config (CircuitBreakerConfig, optional): Configuração personalizada.

        Returns:
            CircuitBreaker: Instância do circuit breaker.

        """
        if name not in self.circuit_breakers:
            config = config or self.default_circuit_config
            self.circuit_breakers[name] = CircuitBreaker(name, config)

        return self.circuit_breakers[name]

    def get_retry_handler(
        self,
        name: str,
        config: RetryConfig | None = None,
    ) -> RetryHandler:
        """Obtém ou cria um retry handler.

        Args:
            name (str): Nome do retry handler.
            config (RetryConfig, optional): Configuração personalizada.

        Returns:
            RetryHandler: Instância do retry handler.

        """
        if name not in self.retry_handlers:
            config = config or self.default_retry_config
            self.retry_handlers[name] = RetryHandler(config)

        return self.retry_handlers[name]

    def resilient_call(
        self,
        func: Callable,
        circuit_name: str = "default",
        retry_name: str = "default",
        *args,
        **kwargs,
    ) -> Any:
        """Executa uma função com proteção completa de resiliência.

        Args:
            func (Callable): Função a ser executada.
            circuit_name (str): Nome do circuit breaker.
            retry_name (str): Nome do retry handler.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Returns:
            Any: Resultado da função.

        """
        circuit_breaker = self.get_circuit_breaker(circuit_name)
        retry_handler = self.get_retry_handler(retry_name)

        def protected_func(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)

        return retry_handler.call(protected_func, *args, **kwargs)

    def get_status(self) -> dict[str, Any]:
        """Retorna o status de todos os circuit breakers."""
        return {
            "circuit_breakers": {
                name: cb.get_status() for name, cb in self.circuit_breakers.items()
            },
            "retry_handlers": {
                name: f"RetryHandler(max_retries={rh.config.max_retries})"
                for name, rh in self.retry_handlers.items()
            },
        }


# Decoradores para facilitar o uso
def resilient(circuit_name: str = "default", retry_name: str = "default"):
    """Decorador para aplicar resiliência a uma função.

    Args:
        circuit_name (str): Nome do circuit breaker.
        retry_name (str): Nome do retry handler.

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Cria um gerenciador temporário se não existir
            if not hasattr(wrapper, "_resilience_manager"):
                wrapper._resilience_manager = ResilienceManager()

            return wrapper._resilience_manager.resilient_call(
                func,
                circuit_name,
                retry_name,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


def circuit_breaker(name: str, config: CircuitBreakerConfig | None = None):
    """Decorador para aplicar apenas circuit breaker.

    Args:
        name (str): Nome do circuit breaker.
        config (CircuitBreakerConfig, optional): Configuração personalizada.

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not hasattr(wrapper, "_circuit_breaker"):
                config_obj = config or CircuitBreakerConfig()
                wrapper._circuit_breaker = CircuitBreaker(name, config_obj)

            return wrapper._circuit_breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


def retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorador para aplicar apenas retry logic.

    Args:
        max_retries (int): Número máximo de tentativas.
        base_delay (float): Delay base em segundos.

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not hasattr(wrapper, "_retry_handler"):
                config = RetryConfig(max_retries=max_retries, base_delay=base_delay)
                wrapper._retry_handler = RetryHandler(config)

            return wrapper._retry_handler.call(func, *args, **kwargs)

        return wrapper

    return decorator


# Instância global do gerenciador de resiliência
resilience_manager = ResilienceManager()
