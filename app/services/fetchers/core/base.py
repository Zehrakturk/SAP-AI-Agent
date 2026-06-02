"""
AbstractFetcher — tüm concrete fetcher'ların uyması zorunlu sözleşme.
Strategy'ler (auth, normalizer, param_mapper) constructor'da bağlanır.
"""

from __future__ import annotations

from abc      import ABC, abstractmethod
from typing   import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.fetchers.models.integration_config import IntegrationConfig
    from app.services.fetchers.models.fetch_context     import FetchContext
    from app.services.fetchers.core.result              import FetchResult

from app.services.fetchers.core.exceptions import FetcherError


class AbstractFetcher(ABC):
    """
    Concrete fetcher (SoapFetcher, RestFetcher, ...) bu sınıftan türetilir.
    `SERVICE_TYPE` class değişkeni `@FetcherFactory.register("SOAP")` ile set edilir.
    """

    SERVICE_TYPE: str = ""

    def __init__(self, config: "IntegrationConfig"):
        self.config      = config
        # Strategy'ler — concrete sınıfın factory metotlarıyla üretilir
        self.auth        = self._create_auth_strategy()
        self.normalizer  = self._create_normalizer()
        self.param_mapper = self._create_param_mapper()

    # ─────────────────────────────────────────────────────────────────────
    # Concrete fetcher tarafından doldurulması ZORUNLU metotlar
    # ─────────────────────────────────────────────────────────────────────

    @abstractmethod
    def fetch(self, context: "FetchContext") -> "FetchResult":
        """Asıl veri çekme. Mutlaka FetchResult döner."""
        raise NotImplementedError

    @abstractmethod
    def _create_auth_strategy(self):
        """Bu protokol için varsayılan auth stratejisini üret."""
        raise NotImplementedError

    @abstractmethod
    def _create_normalizer(self):
        """Bu protokol için varsayılan response normalize stratejisini üret."""
        raise NotImplementedError

    @abstractmethod
    def _create_param_mapper(self):
        """Bu protokol için varsayılan parametre eşleme stratejisini üret."""
        raise NotImplementedError

    # ─────────────────────────────────────────────────────────────────────
    # Opsiyonel hook'lar
    # ─────────────────────────────────────────────────────────────────────

    def validate(self, context: "FetchContext") -> None:
        """Ön validasyon — concrete sınıf override edebilir."""
        if not self.config.is_active:
            raise FetcherError(f"Entegrasyon pasif: {self.config.name}")
        if not self.config.get_endpoint():
            raise FetcherError(f"Endpoint tanımsız: {self.config.name}")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.SERVICE_TYPE} id={self.config.id}>"
