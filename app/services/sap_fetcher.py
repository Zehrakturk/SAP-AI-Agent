"""
app/services/sap_fetcher.py — DEPRECATED.

Eski tek-servis fetcher orchestrator'a delege ediyor.
Scheduler buradaki fetch_and_store'u çağırıyordu — fetchers.fetch_all_active'e taşındı.
"""

from __future__ import annotations

import warnings
from datetime import date, timedelta

from app.repositories.integration_repository import IntegrationRepository
from app.services.fetchers.orchestrator      import (
    fetch_integration, fetch_all_active,
)


def fetch_and_store(
    service_name: str | None = None,
    start_date: date | None  = None,
    finish_date: date | None = None,
):
    """DEPRECATED — fetchers.fetch_integration / fetch_all_active kullanın."""
    warnings.warn(
        "sap_fetcher.fetch_and_store → fetchers.fetch_integration / fetch_all_active",
        DeprecationWarning, stacklevel=2,
    )

    # Varsayılan tarih aralığı: son 50 gün
    if start_date is None:
        start_date = date.today() - timedelta(days=50)
    if finish_date is None:
        finish_date = date.today()

    extracted = {
        "istart_date": start_date.isoformat(),
        "ifinish_date"  : finish_date.isoformat(),
    }

    # service_name verilmemişse tüm aktifleri çek (eski davranış: 'Sevkiyat Servisi'),
    # verilmişse o entegrasyonu çek.
    if service_name is None:
        return fetch_all_active()

    # service_name → integration_id
    repo = IntegrationRepository()
    for cfg in repo.list_active():
        if cfg.name == service_name:
            return fetch_integration(cfg.id, extracted)

    return {"status": "error", "message": f"'{service_name}' bulunamadı."}


if __name__ == "__main__":
    print(fetch_all_active())
