"""
FetcherFactory — registry-tabanlı dinamik fetcher üretici.

Yeni bir fetcher eklemek için:
    @FetcherFactory.register("MY_TYPE")
    class MyFetcher(AbstractFetcher): ...

Core kod ASLA değişmez (Open/Closed).
"""

from __future__ import annotations

from typing import Type, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.fetchers.core.base               import AbstractFetcher
    from app.services.fetchers.models.integration_config import IntegrationConfig

from app.services.fetchers.core.exceptions import FetcherError


class FetcherFactory:
    """
    Decorator tabanlı registry.

    Kullanım:
        @FetcherFactory.register("REST")
        class RestFetcher(AbstractFetcher): ...

        fetcher = FetcherFactory.create(config)   # config.service_type='REST' → RestFetcher
    """

    _REGISTRY: Dict[str, Type["AbstractFetcher"]] = {}

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def register(cls, service_type: str):
        """Decorator — concrete fetcher class'ı REGISTRY'e kaydeder."""
        key = service_type.strip().upper()

        def wrapper(fetcher_cls):
            fetcher_cls.SERVICE_TYPE = key
            cls._REGISTRY[key] = fetcher_cls
            return fetcher_cls

        return wrapper

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def create(cls, config: "IntegrationConfig") -> "AbstractFetcher":
        """
        config.service_type → REGISTRY → instance.
        Bilinmeyen tip → FetcherError.
        """
        service_type = (config.service_type or "SOAP").upper()
        fetcher_cls  = cls._REGISTRY.get(service_type)

        if not fetcher_cls:
            available = ", ".join(sorted(cls._REGISTRY.keys())) or "(boş)"
            raise FetcherError(
                f"'{service_type}' için fetcher kayıtlı değil. "
                f"Mevcut tipler: {available}"
            )

        return fetcher_cls(config)

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def supported_types(cls) -> list[str]:
        """Şu an kayıtlı tüm fetcher tiplerini döner."""
        return sorted(cls._REGISTRY.keys())

    @classmethod
    def is_registered(cls, service_type: str) -> bool:
        return service_type.upper() in cls._REGISTRY

    @classmethod
    def clear_registry(cls) -> None:
        """Test amaçlı — registry'i sıfırlar."""
        cls._REGISTRY.clear()
