"""
Circuit breaker pattern para APIs externas.
Previene cascadas de fallos cuando un servicio externo está caído.

Uso:
    breaker = CircuitBreaker("zoho", failure_threshold=5, recovery_timeout=60)

    if not breaker.can_execute():
        return fallback_response()

    try:
        result = await call_external_api()
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise
"""

import time
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(StrEnum):
    CLOSED = "closed"  # Normal — requests pass through
    OPEN = "open"  # Tripped — requests are blocked
    HALF_OPEN = "half_open"  # Testing — one request allowed


class CircuitBreaker:
    """
    Circuit breaker con 3 estados:
    - CLOSED: todo normal, requests pasan
    - OPEN: servicio caído, requests bloqueados (retorna error inmediato)
    - HALF_OPEN: después del recovery_timeout, permite 1 request de prueba
    """

    # Registry global de breakers
    _registry: dict[str, "CircuitBreaker"] = {}

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.total_trips = 0

        # Register
        CircuitBreaker._registry[name] = self

    def can_execute(self) -> bool:
        """Verifica si se puede ejecutar un request."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_half_open", breaker=self.name)
                return True
            return False

        # HALF_OPEN — allow one request
        return True

    def record_success(self):
        """Registra un request exitoso."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("circuit_closed", breaker=self.name)
        self.success_count += 1

    def record_failure(self):
        """Registra un request fallido."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("circuit_reopened", breaker=self.name)
            return

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.total_trips += 1
            logger.warning(
                "circuit_tripped",
                breaker=self.name,
                failures=self.failure_count,
                total_trips=self.total_trips,
            )

    def reset(self):
        """Reset manual del breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        logger.info("circuit_reset", breaker=self.name)

    @property
    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_trips": self.total_trips,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    @classmethod
    def get_all_status(cls) -> list[dict]:
        return [b.status for b in cls._registry.values()]

    @classmethod
    def get(cls, name: str) -> "CircuitBreaker | None":
        return cls._registry.get(name)


# ─── Pre-configured breakers for external services ──────────────────────────

zoho_breaker = CircuitBreaker("zoho", failure_threshold=5, recovery_timeout=60)
meta_breaker = CircuitBreaker("meta_whatsapp", failure_threshold=3, recovery_timeout=30)
openai_breaker = CircuitBreaker("openai", failure_threshold=3, recovery_timeout=45)
botmaker_breaker = CircuitBreaker("botmaker", failure_threshold=5, recovery_timeout=60)
