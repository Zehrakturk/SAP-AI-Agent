"""
gap_detector — eksik veri tespiti.

Sorgu 0 satır döndüğünde, bu gerçekten "veri yok" mu yoksa "henüz çekilmedi" mi?
  - Eşleşen entegrasyon istenen tarih aralığını çekebiliyor (config + fetchable)
  - VE fetch_log'da bu (integration_id, param_hash) yok
  → eksik veri (GapResult). Aksi halde gerçekten veri yok → None.
"""

from __future__ import annotations

import calendar
import datetime as _dt

from app.services.ingestion.models                  import GapResult
from app.services.fetchers.models.fetch_context      import FetchContext
from app.services.fetchers.persistence.fetch_logger  import FetchLogger


_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
    "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}


def _month_range_from_question(question: str, year: int | None = None) -> dict | None:
    """'mart ayı verileri ...' gibi sorgulardan ay aralığı türetir."""
    ql = (question or "").lower()
    for name, m in _TR_MONTHS.items():
        if name in ql:
            y = year or _dt.date.today().year
            # Soruda 4 haneli yıl geçtiyse onu kullan
            import re as _re
            ym = _re.search(r"\b(20\d{2})\b", ql)
            if ym:
                y = int(ym.group(1))
            last = calendar.monthrange(y, m)[1]
            return {"start_date": f"{y}-{m:02d}-01", "end_date": f"{y}-{m:02d}-{last:02d}"}
    return None


def _extract_params(intent: dict, filters: dict,
                    question: str | None = None) -> dict | None:
    """
    Tarih aralığını şu öncelikle çıkarır:
      1. intent.donemler  2. filters.start/end  3. soru metnindeki Türkçe ay adı
    Hiçbiri yoksa None (tarihsiz sorguda gap-onayı tetiklenmez).
    """
    donemler = (intent or {}).get("donemler") or []
    if donemler:
        start = donemler[0].get("baslangic")
        end   = donemler[-1].get("bitis")
        if start and end:
            return {"start_date": start, "end_date": end}

    f = filters or {}
    if f.get("start_date") and f.get("end_date"):
        return {"start_date": f["start_date"], "end_date": f["end_date"]}

    # Fallback: soru metninden ay adı
    return _month_range_from_question(question)


def _is_fetchable(config) -> bool:
    """Entegrasyonun veri çekebilecek bir endpoint'i var mı?"""
    if config is None:
        return False
    stype = (getattr(config, "service_type", "") or "").upper()
    wsdl  = getattr(config, "wsdl_url", "") or ""
    extra = getattr(config, "extra_config", {}) or {}
    # SOAP → wsdl_url; REST/ODATA → wsdl_url (base_url) veya extra_config.base_url
    return bool(wsdl or extra.get("base_url") or stype in ("REST", "ODATA", "SOAP"))


def detect_gap(intent: dict, matched_ids: list[int],
               filters: dict | None = None,
               today: _dt.date | None = None,
               question: str | None = None) -> GapResult | None:
    """
    Eksik veri varsa GapResult, yoksa None döner.
    matched_ids: aday entegrasyon id'leri (RAG eşleşmesi veya tüm aktif fallback).
    question   : tarih intent'ten çıkmazsa ay-adı fallback'i için soru metni.
    """
    params = _extract_params(intent or {}, filters or {}, question=question)
    if not params or not matched_ids:
        return None   # backfill edilecek tarih yok ya da hedef entegrasyon yok

    # Lazy import — repository fetchers'a bağımlı (circular import koruması)
    from app.repositories.integration_repository import IntegrationRepository
    repo   = IntegrationRepository()
    logger = FetchLogger()
    ctx    = FetchContext.from_extracted(params)

    for int_id in matched_ids:
        try:
            config = repo.get_with_params(int_id)
        except Exception:
            continue   # pasif/yok

        if not _is_fetchable(config):
            continue

        # Bu parametrelerle daha önce çekildiyse → gerçekten veri yok, onay açma
        try:
            if logger.is_already_fetched(int_id, ctx):
                continue
        except Exception:
            # fetch_log okunamazsa temkinli davran: gap olarak işaretle
            pass

        return GapResult(
            integration_id   = int_id,
            integration_name = getattr(config, "name", f"#{int_id}"),
            params           = params,
            reason           = (
                f"{params['start_date']} – {params['end_date']} aralığı için "
                f"'{getattr(config, 'name', int_id)}' verisi sistemde bulunmuyor; "
                f"SAP'tan çekilmesi admin onayı gerektiriyor."
            ),
        )

    return None
