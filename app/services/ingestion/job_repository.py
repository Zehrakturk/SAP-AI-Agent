"""
JobRepository — ingestion_jobs tablosu CRUD + atomik claim/lock.

Çok worker güvenli: claim_next() tek bir QUEUED job'u atomik olarak RUNNING'e çeker.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.services.db               import get_connection
from app.services.ingestion.models import JobStatus


class JobRepository:

    _ensured = False
    STALE_MINUTES = 10   # bu süreden uzun RUNNING kalan job crash sayılır

    def _ensure_table(self, cursor) -> None:
        if JobRepository._ensured:
            return
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ingestion_jobs')
            CREATE TABLE ingestion_jobs (
                id                  INT IDENTITY(1,1) PRIMARY KEY,
                approval_request_id INT NOT NULL,
                integration_id      INT NOT NULL,
                params_json         NVARCHAR(MAX),
                status              NVARCHAR(20) DEFAULT 'QUEUED',
                attempts            INT DEFAULT 0,
                max_attempts        INT DEFAULT 3,
                rows_written        INT,
                chunks_indexed      INT,
                error_message       NVARCHAR(MAX),
                locked_by           NVARCHAR(80),
                locked_at           DATETIME,
                started_at          DATETIME,
                finished_at         DATETIME,
                created_at          DATETIME DEFAULT GETDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_ij_status')
            CREATE INDEX ix_ij_status ON ingestion_jobs (status)
        """)
        JobRepository._ensured = True

    # ─────────────────────────────────────────────────────────────────────
    def enqueue(self, approval_request_id: int, integration_id: int,
                params: dict) -> int:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                INSERT INTO ingestion_jobs
                  (approval_request_id, integration_id, params_json, status)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, 'QUEUED')
            """, (int(approval_request_id), int(integration_id),
                  json.dumps(params or {}, ensure_ascii=False, default=str)))
            new_id = int(cursor.fetchone()[0])
            conn.commit()
            return new_id
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def reclaim_stale(self) -> int:
        """
        Crash sonrası kilitli kalmış (RUNNING/... + locked_at eski) job'ları
        QUEUED'a geri çeker. Döner: kurtarılan satır sayısı.
        """
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute(f"""
                UPDATE ingestion_jobs
                   SET status='QUEUED', locked_by=NULL, locked_at=NULL
                 WHERE status IN ('RUNNING','FETCHING','INDEXING','RERUNNING')
                   AND locked_at IS NOT NULL
                   AND locked_at < DATEADD(MINUTE, -{self.STALE_MINUTES}, GETDATE())
            """)
            n = cursor.rowcount
            conn.commit()
            return n
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def claim_next(self, worker_id: str) -> dict | None:
        """
        Tek bir QUEUED job'u atomik olarak RUNNING'e çeker (single-flight).
        Backoff: attempts>0 ise locked_at(son deneme)+2^attempts dk dolmadan alınmaz.
        Döner: claim edilen job dict'i veya None.
        """
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            # Backoff penceresi: son denemeden (locked_at) bu yana yeterli süre geçti mi?
            cursor.execute("""
                UPDATE TOP (1) ingestion_jobs
                   SET status='RUNNING', locked_by=?, locked_at=GETDATE(),
                       started_at=GETDATE(), attempts = attempts + 1
                OUTPUT INSERTED.id, INSERTED.approval_request_id, INSERTED.integration_id,
                       INSERTED.params_json, INSERTED.attempts, INSERTED.max_attempts
                 WHERE status='QUEUED' AND locked_by IS NULL
                   AND (
                        locked_at IS NULL
                        OR DATEADD(MINUTE, CAST(POWER(2, attempts) AS INT), locked_at) <= GETDATE()
                   )
            """, (worker_id[:80],))
            row = cursor.fetchone()
            conn.commit()
            if not row:
                return None
            return {
                "id"                 : int(row[0]),
                "approval_request_id": int(row[1]),
                "integration_id"     : int(row[2]),
                "params"             : json.loads(row[3]) if row[3] else {},
                "attempts"           : int(row[4]),
                "max_attempts"       : int(row[5]),
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def set_status(self, job_id: int, status: str, **fields) -> None:
        """status + opsiyonel alanları (rows_written, chunks_indexed, error_message) günceller."""
        sets   = ["status = ?"]
        params : list = [status]
        for col in ("rows_written", "chunks_indexed", "error_message"):
            if col in fields:
                sets.append(f"{col} = ?")
                params.append(fields[col])
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            sets.append("finished_at = GETDATE()")
        params.append(int(job_id))

        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute(
                f"UPDATE ingestion_jobs SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

    def requeue_for_retry(self, job_id: int, error: str) -> None:
        """Hata sonrası: kilidi bırak, QUEUED'a geri koy (attempts korunur, backoff için locked_at kalır)."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                UPDATE ingestion_jobs
                   SET status='QUEUED', locked_by=NULL, error_message=?
                 WHERE id = ?
            """, ((error or "")[:4000], int(job_id)))
            conn.commit()
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def get_by_id(self, job_id: int) -> dict | None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (int(job_id),))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cursor.description]
            d = dict(zip(cols, row))
            for k in ("created_at", "started_at", "finished_at", "locked_at"):
                if isinstance(d.get(k), datetime):
                    d[k] = d[k].isoformat()
            if d.get("params_json"):
                try: d["params"] = json.loads(d["params_json"])
                except Exception: d["params"] = {}
            d.pop("params_json", None)
            return d
        finally:
            conn.close()

    def get_by_approval(self, approval_request_id: int) -> dict | None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute(
                "SELECT TOP 1 id FROM ingestion_jobs "
                "WHERE approval_request_id = ? ORDER BY id DESC",
                (int(approval_request_id),),
            )
            row = cursor.fetchone()
            return self.get_by_id(int(row[0])) if row else None
        finally:
            conn.close()
