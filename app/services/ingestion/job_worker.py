"""
job_worker — ingestion_jobs kuyruğunu işleyen worker.

process_pending_jobs() APScheduler tarafından periyodik (5 sn) çağrılır.
Her tick:
  1. Housekeeping: stale-lock kurtarma + süresi geçmiş onayları EXPIRED yapma
  2. Bir QUEUED job'u atomik claim et (çok worker güvenli)
  3. FETCH+WRITE → (koşullu) INDEX → RERUN → result kaydet → COMPLETED
  4. Hata: max_attempts altında QUEUED'a geri (backoff), üstünde FAILED
"""

from __future__ import annotations

import os
import socket
import traceback

from app.services.db                             import get_connection
from app.services.ingestion.models               import JobStatus, AuditAction
from app.services.ingestion.job_repository        import JobRepository
from app.services.ingestion.approval_repository   import ApprovalRepository
from app.services.ingestion.audit_repository      import AuditRepository

_WORKER_ID  = f"{socket.gethostname()}-{os.getpid()}"
_MAX_PER_TICK = 5   # bir tick'te en fazla bu kadar job (kuyruğu boğmamak için)


def _worker_id() -> str:
    return _WORKER_ID


# ─────────────────────────────────────────────────────────────────────────────
def _vector_count(integration_id: int) -> int:
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM integration_vectors WHERE integration_id = ?",
            (integration_id,),
        )
        n = int(cursor.fetchone()[0] or 0)
        conn.close()
        return n
    except Exception:
        return -1   # tablo yok / okunamadı


def _schema_exists(integration_id: int) -> bool:
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TOP 1 1 FROM integration_schemas WHERE integration_id = ?",
            (integration_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
def process_pending_jobs() -> dict:
    """APScheduler tick. Döner: bu tick'te işlenen job özeti (debug)."""
    jobs_repo = JobRepository()
    appr_repo = ApprovalRepository()
    audit     = AuditRepository()

    # Housekeeping (hatalar yutulur — tick asla patlamamalı)
    try:
        reclaimed = jobs_repo.reclaim_stale()
        if reclaimed:
            print(f"[WORKER] {reclaimed} stale job QUEUED'a kurtarıldı.")
    except Exception as e:
        print(f"[WORKER] reclaim_stale hata: {e}")
    try:
        appr_repo.expire_overdue()
    except Exception:
        pass

    processed = []
    for _ in range(_MAX_PER_TICK):
        try:
            job = jobs_repo.claim_next(_worker_id())
        except Exception as e:
            print(f"[WORKER] claim hata: {e}")
            break
        if not job:
            break
        result = _run_job(job, jobs_repo, appr_repo, audit)
        processed.append(result)

    return {"worker": _worker_id(), "processed": processed}


# ─────────────────────────────────────────────────────────────────────────────
def _run_job(job: dict, jobs_repo: JobRepository,
             appr_repo: ApprovalRepository, audit: AuditRepository) -> dict:
    job_id   = job["id"]
    appr_id  = job["approval_request_id"]
    int_id   = job["integration_id"]
    params   = job["params"] or {}
    attempts = job["attempts"]
    max_att  = job["max_attempts"]

    audit.log("ingestion_job", job_id, AuditAction.JOB_CLAIMED,
              actor=_worker_id(), detail={"attempt": attempts})

    try:
        # 1) FETCH + WRITE ----------------------------------------------------
        jobs_repo.set_status(job_id, JobStatus.FETCHING)
        from app.services.fetchers import fetch_integration

        had_vectors = _vector_count(int_id) > 0   # fetch öncesi indeks durumu
        fetch_res = fetch_integration(int_id, params, force=True)

        if fetch_res.get("status") == "error":
            raise RuntimeError(fetch_res.get("message") or "Fetch hatası")

        rows_written = int(fetch_res.get("rows_written") or 0)
        jobs_repo.set_status(job_id, JobStatus.FETCHING, rows_written=rows_written)
        audit.log("ingestion_job", job_id, AuditAction.FETCH_DONE,
                  actor=_worker_id(),
                  detail={"rows_written": rows_written,
                          "target_table": fetch_res.get("target_table")})

        # 2) INDEX (koşullu) --------------------------------------------------
        # Sadece YENİ entegrasyon/şema: daha önce hiç vektörü yoksa ve şema oluştuysa.
        # Var olan tabloya tarih backfill'inde embedding GEREKMEZ (RAG şemayı embed eder).
        chunks = None
        if not had_vectors and _schema_exists(int_id):
            jobs_repo.set_status(job_id, JobStatus.INDEXING)
            try:
                from app.services.qdrant_indexer import index_integration
                chunks = index_integration(int_id)
                jobs_repo.set_status(job_id, JobStatus.INDEXING, chunks_indexed=chunks)
                audit.log("ingestion_job", job_id, AuditAction.INDEXED,
                          actor=_worker_id(), detail={"chunks": chunks})
            except Exception as ie:
                # İndeksleme başarısızsa job'u komple düşürme — veri yazıldı, log'la geç
                print(f"[WORKER] index_integration({int_id}) hata: {ie}")
                audit.log("ingestion_job", job_id, AuditAction.INDEXED,
                          actor=_worker_id(), detail={"error": str(ie)})

        # 3) RERUN — orijinal sorguyu taze çalıştır ---------------------------
        jobs_repo.set_status(job_id, JobStatus.RERUNNING)
        appr = appr_repo.get_by_id(appr_id)
        rerun_result = {}
        if appr:
            from app.services.query_engine import ask
            from app.models.store import company_of
            _company = company_of(appr.get("user_id"))   # talep sahibinin firması
            rerun_result = ask(
                appr.get("question") or "",
                filters     = appr.get("filters") or {},
                approval_mode = False,     # tekrar onay döngüsüne girme
                force_fresh   = True,      # cache'i atla, taze çalıştır
                company       = _company,  # firma izolasyonu
            )
            appr_repo.set_result(appr_id, rerun_result)
        audit.log("ingestion_job", job_id, AuditAction.RERUN, actor=_worker_id(),
                  detail={"rows": rerun_result.get("count") if rerun_result else None})

        # 4) COMPLETED --------------------------------------------------------
        jobs_repo.set_status(job_id, JobStatus.COMPLETED)
        audit.log("approval_request", appr_id, AuditAction.COMPLETED,
                  actor=_worker_id(),
                  detail={"job_id": job_id, "rows_written": rows_written,
                          "chunks_indexed": chunks})
        return {"job_id": job_id, "status": "COMPLETED", "rows": rows_written}

    except Exception as e:
        err = f"{e}"
        print(f"[WORKER] job#{job_id} hata (attempt {attempts}/{max_att}): {err}")
        traceback.print_exc()
        if attempts >= max_att:
            jobs_repo.set_status(job_id, JobStatus.FAILED, error_message=err[:4000])
            audit.log("ingestion_job", job_id, AuditAction.FAILED,
                      actor=_worker_id(), detail={"error": err, "attempts": attempts})
            return {"job_id": job_id, "status": "FAILED", "error": err}
        else:
            jobs_repo.requeue_for_retry(job_id, err)
            audit.log("ingestion_job", job_id, AuditAction.RETRY,
                      actor=_worker_id(), detail={"error": err, "attempt": attempts})
            return {"job_id": job_id, "status": "RETRY", "error": err}
