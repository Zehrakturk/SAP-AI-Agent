"""
Orchestrator — fetcher modülünün tek public giriş noktası.

Tüm üst katmanlar (API, scheduler, query_engine) buradaki iki fonksiyonu çağırır:
  - fetch_integration(integration_id, extracted_params, force)
  - fetch_all_active()
"""

from __future__ import annotations

from app.services.fetchers.core.factory                import FetcherFactory
from app.services.fetchers.core.exceptions             import FetcherError
from app.services.fetchers.models.fetch_context        import FetchContext
from app.services.fetchers.persistence.data_writer     import DataWriter
from app.services.fetchers.persistence.fetch_logger    import FetchLogger


def _get_repo():
    """Lazy import — repositories modülü fetchers'a bağımlı olduğu için."""
    from app.repositories.integration_repository import IntegrationRepository
    return IntegrationRepository()


def fetch_integration(integration_id: int,
                      extracted_params: dict | None = None,
                      force: bool = False) -> dict:    # noqa: E501
    """
    Bir entegrasyonu çalıştırır, veriyi MSSQL'e yazar, log'a düşer.

    Döner:
      {
        "status"      : "fetched" | "cached" | "error",
        "rows_written": N,
        "target_table": "...",
        "fetcher"     : "SOAP" | "REST" | ...,
        "message"     : "..."  (opsiyonel)
      }
    """
    extracted_params = extracted_params or {}

    try:
        # 1. Config + paramları DB'den oku
        repo    = _get_repo()
        config  = repo.get_with_params(integration_id)
        context = FetchContext.from_extracted(extracted_params)
        logger  = FetchLogger()

        target_table = config.effective_target_table()

        # 2. Cache kontrolü — extracted'a göre hash al
        if not force and logger.is_already_fetched(integration_id, context):
            print(f"[CACHE HIT] {config.name} — extracted={extracted_params}")
            cached = logger.get_cached_result(integration_id, context)
            cached.setdefault("target_table", target_table)
            cached.setdefault("fetcher", config.service_type)
            return cached

        # 3. Factory'den fetcher al
        fetcher = FetcherFactory.create(config)
        print(f"[FETCH] {config.name} ({config.service_type}) → "
              f"extracted={extracted_params}")

        # 4. Veriyi çek
        result = fetcher.fetch(context)

        if not result.records:
            # Yine de cache kaydı düş (boş sonuç) — gereksiz tekrar çağrıyı önler
            logger.record(integration_id, context,
                          rows_written=0,
                          target_table=target_table,
                          call_params=result.call_params)
            return {
                "status"      : "fetched",
                "rows_written": 0,
                "target_table": target_table,
                "fetcher"     : config.service_type,
                "message"     : "Servisten veri gelmedi.",
            }

        # 5. MSSQL'e yaz — param_hash call_params'a göre
        p_hash = context.param_hash(integration_id, result.call_params)
        writer = DataWriter(target_table=target_table)
        rows_written = writer.write(
            records        = result.records,
            integration_id = integration_id,
            param_hash     = p_hash,
        )

        # 6. Log
        logger.record(integration_id, context,
                      rows_written=rows_written,
                      target_table=target_table,
                      call_params=result.call_params)

        return {
            "status"      : "fetched",
            "rows_written": rows_written,
            "target_table": target_table,
            "fetcher"     : config.service_type,
        }

    except FetcherError as e:
        return {"status": "error", "message": str(e),
                "target_table": "", "fetcher": "",
                "attempted_params": _safe_attempt_params(integration_id, extracted_params),
                "extracted_params": extracted_params}
    except Exception as e:
        print(f"[ORCHESTRATOR] Beklenmeyen hata: {e}")
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e),
                "target_table": "", "fetcher": "",
                "attempted_params": _safe_attempt_params(integration_id, extracted_params),
                "extracted_params": extracted_params}


def _safe_attempt_params(integration_id: int, extracted_params: dict) -> dict:
    """
    Hata durumunda debug için: param mapper'ın ne üreteceğini hesaplar.
    Hiç patlamamalı — patlarsa boş dict döner.
    """
    try:
        cfg = _get_repo().get_with_params(integration_id)
        f   = FetcherFactory.create(cfg)
        return f.param_mapper.map(cfg.params, extracted_params)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
def fetch_all_active() -> dict:
    """
    is_active=1 olan tüm entegrasyonları varsayılan parametrelerle çeker.
    Scheduled job için ideal — her entegrasyon kendi defaults'unu kullanır.
    """
    repo    = _get_repo()
    results = {}

    for config in repo.list_active():
        try:
            res = fetch_integration(
                integration_id   = config.id,
                extracted_params = {},   # defaults kullanılır
                force            = False,
            )
            results[config.name] = {"status": "ok", **res}
        except Exception as e:
            results[config.name] = {"status": "error", "message": str(e)}

    return results


# ─────────────────────────────────────────────────────────────────────────────
def get_integration_target_table(integration_id: int) -> str | None:
    """
    Eski dynamic_fetcher.get_integration_target_table() geriye uyumluluğu.
    """
    try:
        repo   = IntegrationRepository()
        config = repo.get_with_params(integration_id)
        return config.effective_target_table()
    except Exception:
        return None
