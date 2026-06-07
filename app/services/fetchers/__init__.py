"""
app/services/fetchers/

Dinamik fetcher modülü. Factory + Strategy pattern.

Public API:
    fetch_integration(integration_id, extracted_params, force=False) -> dict
    fetch_all_active() -> dict
    FetcherFactory   — registry-tabanlı factory
"""

# Concrete fetcher'lar import edilince @FetcherFactory.register decorator'ı çalışır
# ve REGISTRY otomatik dolar. Bu satır KRİTİK.
from app.services.fetchers.implementations import *  # noqa: F401,F403

from app.services.fetchers.orchestrator    import (
    fetch_integration, fetch_all_active, query_integration_live,
)
from app.services.fetchers.core.factory    import FetcherFactory

__all__ = ["fetch_integration", "fetch_all_active", "query_integration_live", "FetcherFactory"]
