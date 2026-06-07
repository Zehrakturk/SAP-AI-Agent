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


def _table_items(node):
    """SAP envelope tablosundan satırları çıkarır ({item:[...]} / liste / tekil)."""
    if isinstance(node, dict) and "item" in node:
        it = node["item"]
        if it is None:
            return []
        return it if isinstance(it, list) else [it]
    if isinstance(node, list):
        return node
    return []


_VENDOR_TABLE_KEYS = ("ET_RETURN_VENDOR", "ET_VENDOR", "ET_LIFNR", "ET_RETURN_LIFNR")
_VENDOR_CODE_FIELDS = ("VENDOR", "LIFNR")
_NAME_HINTS = ("NAME", "BEZEI", "TXT", "TEXT", "VTEXT", "ADI", "TITLE", "UNVAN")


def _build_vendor_name_map(raw: dict) -> dict:
    """
    ET_RETURN_VENDOR (satıcı kodu → satıcı adı) tablosundan eşleme üretir.
    Alan adları sabit değildir: anahtar = VENDOR/LIFNR; isim = ad-benzeri (NAME/TXT/BEZEI…)
    veya VENDOR dışındaki ilk dolu metin alanı.
    """
    node = None
    if isinstance(raw, dict):
        for k in _VENDOR_TABLE_KEYS:
            if raw.get(k) is not None:
                node = raw[k]
                break
    if node is None:
        return {}
    out = {}
    for r in _table_items(node):
        if not isinstance(r, dict):
            continue
        code = ""
        for kf in r:
            if kf.upper() in _VENDOR_CODE_FIELDS:
                code = str(r.get(kf) or "").strip()
                break
        if not code:
            continue
        name = None
        for kf in r:                         # önce ad-benzeri alan
            if kf.upper() in _VENDOR_CODE_FIELDS:
                continue
            val = r.get(kf)
            if val in (None, ""):
                continue
            if any(h in kf.upper() for h in _NAME_HINTS):
                name = str(val).strip()
                break
        if name is None:                     # yoksa VENDOR dışı ilk dolu alan
            for kf in r:
                if kf.upper() in _VENDOR_CODE_FIELDS:
                    continue
                if r.get(kf) not in (None, ""):
                    name = str(r.get(kf)).strip()
                    break
        if name:
            out[code] = name
    return out


def query_integration_live(integration_id: int,
                           extracted_params: dict | None = None) -> dict:
    """
    CANLI (anlık) sorgu — SQL'e YAZMADAN servisten o an veri çeker.
    Cache yok, DataWriter yok, fetch_log yok. SAP skalar dönüşleri (EV_SUCCESS/EV_MESSAGE/
    EV_COUNT) ham yanıttan çıkarılır.

    Döner:
      {"status":"ok","records":[...],"success":bool,"message":str|None,
       "count":int,"call_params":{...}}  ya da  {"status":"error","message":...}
    """
    extracted_params = extracted_params or {}
    try:
        repo    = _get_repo()
        config  = repo.get_with_params(integration_id)

        # CANLI çağrıda TÜM parametreler gönderilir (verilmeyenler BOŞ STRING) →
        # SAP envelope'u beklenen biçimde oluşur: <IV_FISCPER></IV_FISCPER> gibi tüm
        # IV_* elemanları mevcut. (Mapper aksi halde boşları atlar, eksik eleman gönderir.)
        full = dict(extracted_params)
        for p in config.params:
            k = (p.param_name or "").lower()
            if k and k not in full:
                full[k] = ""

        context = FetchContext.from_extracted(full)
        fetcher = FetcherFactory.create(config)
        print(f"[LIVE] {config.name} ({config.service_type}) ← extracted={full}")

        result = fetcher.fetch(context)
        raw    = result.raw_response or {}

        def _g(*keys):
            if isinstance(raw, dict):
                for k in keys:
                    if raw.get(k) is not None:
                        return raw[k]
            return None

        success_raw = _g("EV_SUCCESS", "EV_SUCESS", "SUCCESS")
        success = (str(success_raw).strip().upper() in ("X", "TRUE", "1", "S", "Y", "E")
                   if success_raw is not None else True)
        message = _g("EV_MESSAGE", "MESSAGE", "EV_MSG")
        count   = _g("EV_COUNT", "COUNT")

        # ET_RETURN_VENDOR varsa: VENDOR kodunu satıcı ADIYLA eşleştir → kayıtlara SATICI_ADI ekle
        vmap = _build_vendor_name_map(raw)
        if vmap:
            matched = 0
            for rec in result.records:
                if not isinstance(rec, dict):
                    continue
                code = str(rec.get("VENDOR") or "").strip()
                if code and code in vmap:
                    rec["SATICI_ADI"] = vmap[code]
                    matched += 1
            print(f"[LIVE] ET_RETURN_VENDOR: {len(vmap)} satıcı adı, {matched} kayıt eşleşti")

        return {
            "status": "ok",
            "records": result.records,
            "vendor_map": vmap,
            "success": success,
            "message": message,
            "count": int(count) if count is not None else len(result.records),
            "call_params": result.call_params,
        }
    except FetcherError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e)}


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
def fetch_all_active(incremental: bool = True) -> dict:
    """
    is_active=1 olan tüm entegrasyonları çeker.
    incremental=True (varsayılan): her entegrasyon için watermark'tan (hedef tablodaki
      en son tarih) itibaren YALNIZ yeni veri çekilir → tekrar çekme/şişme önlenir.
      Tarih param'ı / verisi olmayanlar otomatik kendi defaults'una düşer.
    incremental=False: eski davranış — herkes defaults ({}) ile.
    """
    repo    = _get_repo()
    results = {}

    for config in repo.list_active():
        try:
            # Canlı (anlık) sorgu entegrasyonları gece çekilmez — SQL'e yazılmaz
            if (config.extra_config or {}).get("live_query"):
                results[config.name] = {"status": "skipped", "reason": "live_query"}
                continue
            extracted = {}
            if incremental:
                try:
                    from app.services.lifecycle.watermark import incremental_params
                    extracted = incremental_params(config)
                except Exception as we:
                    print(f"[INCREMENTAL] {config.name} watermark atlandı: {we}")
                    extracted = {}
            res = fetch_integration(
                integration_id   = config.id,
                extracted_params = extracted,
                force            = False,
            )
            results[config.name] = {"status": "ok", "incremental": bool(extracted), **res}
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
