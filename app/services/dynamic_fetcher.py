"""
app/services/dynamic_fetcher.py — DEPRECATED.

Eski monolitik fetcher 'app/services/fetchers/' modülüne taşındı.
Bu dosya geriye uyumluluk için ince bir shim.

Yeni kod kullanımı:
    from app.services.fetchers import fetch_integration, fetch_all_active
"""

from __future__ import annotations
import warnings

from app.services.fetchers.orchestrator import (
    fetch_integration         as _fetch_integration,
    get_integration_target_table as _get_target_table,
)
from app.services.fetchers.models.fetch_context import FetchContext
from app.services.fetchers.persistence.fetch_logger import FetchLogger


def fetch_on_demand(integration_id: int, extracted_params: dict,
                    force: bool = False) -> dict:
    """DEPRECATED — fetchers.fetch_integration kullanın."""
    warnings.warn(
        "dynamic_fetcher.fetch_on_demand → fetchers.fetch_integration",
        DeprecationWarning, stacklevel=2,
    )
    return _fetch_integration(integration_id, extracted_params, force=force)


def get_integration_target_table(integration_id: int) -> str | None:
    return _get_target_table(integration_id)


def is_data_available(integration_id: int, extracted_params: dict) -> bool:
    """Eski API uyumluluğu — FetchLogger ile aynı sorunun cevabı."""
    context = FetchContext.from_extracted(extracted_params)
    return FetchLogger().is_already_fetched(integration_id, context)
