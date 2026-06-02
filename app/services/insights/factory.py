"""
InsightDetectorFactory — registry tabanlı detector kayıt sistemi.
FetcherFactory ile aynı pattern.
"""

from __future__ import annotations

from typing import Type, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.insights.base import AbstractInsightDetector


class InsightDetectorFactory:
    """
    Yeni detector ekleme:
        @InsightDetectorFactory.register("trend_change")
        class TrendChangeDetector(AbstractInsightDetector): ...
    """

    _REGISTRY: Dict[str, Type["AbstractInsightDetector"]] = {}

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def register(cls, name: str):
        key = name.strip().lower()

        def wrapper(detector_cls):
            detector_cls.DETECTOR_NAME = key
            cls._REGISTRY[key] = detector_cls
            return detector_cls

        return wrapper

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def create(cls, name: str) -> "AbstractInsightDetector":
        key = name.strip().lower()
        d_cls = cls._REGISTRY.get(key)
        if not d_cls:
            available = ", ".join(sorted(cls._REGISTRY.keys())) or "(boş)"
            raise ValueError(f"'{name}' detector kayıtlı değil. Mevcut: {available}")
        return d_cls()

    @classmethod
    def all_instances(cls) -> list["AbstractInsightDetector"]:
        """Kayıtlı tüm detector'ların instance'larını döner."""
        return [d_cls() for d_cls in cls._REGISTRY.values()]

    @classmethod
    def supported_names(cls) -> list[str]:
        return sorted(cls._REGISTRY.keys())
