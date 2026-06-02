"""
ApprovalRepository — approval_requests tablosu CRUD + dedup.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.services.db                  import get_connection
from app.services.ingestion.models    import ApprovalStatus, ApprovalRequest


class ApprovalRepository:

    _ensured = False

    def _ensure_table(self, cursor) -> None:
        if ApprovalRepository._ensured:
            return
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'approval_requests')
            CREATE TABLE approval_requests (
                id                    INT IDENTITY(1,1) PRIMARY KEY,
                external_id           NVARCHAR(40) NOT NULL,
                request_hash          NVARCHAR(32) NOT NULL,
                user_id               NVARCHAR(50),
                question              NVARCHAR(MAX),
                filters_json          NVARCHAR(MAX),
                integration_id        INT,
                requested_params_json NVARCHAR(MAX),
                reason                NVARCHAR(500),
                status                NVARCHAR(20) DEFAULT 'PENDING',
                decided_by            NVARCHAR(50),
                decided_at            DATETIME,
                decision_note         NVARCHAR(500),
                result_json           NVARCHAR(MAX),
                session_id            NVARCHAR(40),
                created_at            DATETIME DEFAULT GETDATE(),
                expires_at            DATETIME
            )
        """)
        # session_id kolonu yoksa ekle (geriye uyum)
        cursor.execute("""
            IF COL_LENGTH('approval_requests', 'session_id') IS NULL
                ALTER TABLE approval_requests ADD session_id NVARCHAR(40) NULL
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_ar_status')
            CREATE INDEX ix_ar_status ON approval_requests (status)
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_ar_hash')
            CREATE INDEX ix_ar_hash ON approval_requests (request_hash)
        """)
        ApprovalRepository._ensured = True

    # ─────────────────────────────────────────────────────────────────────
    def find_open_by_hash(self, request_hash: str) -> dict | None:
        """Aynı hash'te PENDING veya APPROVED talep varsa döner (dedup)."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute(
                "SELECT TOP 1 * FROM approval_requests "
                "WHERE request_hash = ? AND status IN ('PENDING','APPROVED') "
                "ORDER BY id DESC",
                (request_hash,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def create(self, req: ApprovalRequest) -> dict:
        """Yeni approval_request ekler, oluşan satırı döner."""
        req.ensure_hash()
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                INSERT INTO approval_requests
                  (external_id, request_hash, user_id, question, filters_json,
                   integration_id, requested_params_json, reason, status, session_id, expires_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.external_id, req.request_hash, req.user_id,
                (req.question or "")[:4000],
                json.dumps(req.filters or {}, ensure_ascii=False, default=str),
                req.integration_id,
                json.dumps(req.requested_params or {}, ensure_ascii=False, default=str),
                (req.reason or "")[:500], req.status, req.session_id, req.expires_at(),
            ))
            new_id = int(cursor.fetchone()[0])
            conn.commit()
            return self.get_by_id(new_id)
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def get_by_id(self, approval_id: int) -> dict | None:
        return self._get_one("id = ?", (int(approval_id),))

    def get_by_external(self, external_id: str) -> dict | None:
        return self._get_one("external_id = ?", (external_id,))

    def _get_one(self, where: str, params: tuple) -> dict | None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute(f"SELECT * FROM approval_requests WHERE {where}", params)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def list_by_status(self, status: str | None = None, limit: int = 50) -> list[dict]:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            if status:
                cursor.execute(
                    f"SELECT TOP {int(limit)} * FROM approval_requests "
                    f"WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor.execute(
                    f"SELECT TOP {int(limit)} * FROM approval_requests "
                    f"ORDER BY created_at DESC"
                )
            cols = [c[0] for c in cursor.description]
            return [self._row_to_dict_cols(cols, r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def list_by_session(self, session_id: str, user_id: str | None = None,
                        limit: int = 20) -> list[dict]:
        """Bir sohbete ait onay taleplerini döner (kart yeniden çizimi için)."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            if user_id is not None:
                cursor.execute(
                    f"SELECT TOP {int(limit)} * FROM approval_requests "
                    f"WHERE session_id = ? AND user_id = ? ORDER BY id ASC",
                    (session_id, str(user_id)),
                )
            else:
                cursor.execute(
                    f"SELECT TOP {int(limit)} * FROM approval_requests "
                    f"WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                )
            cols = [c[0] for c in cursor.description]
            return [self._row_to_dict_cols(cols, r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def update_status(self, approval_id: int, status: str,
                       decided_by: str | None = None,
                       decision_note: str | None = None) -> None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                UPDATE approval_requests
                   SET status = ?, decided_by = ?, decided_at = GETDATE(),
                       decision_note = ?
                 WHERE id = ?
            """, (status, decided_by, (decision_note or "")[:500] or None, int(approval_id)))
            conn.commit()
        finally:
            conn.close()

    def set_result(self, approval_id: int, result: dict) -> None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute(
                "UPDATE approval_requests SET result_json = ? WHERE id = ?",
                (json.dumps(result, ensure_ascii=False, default=str), int(approval_id)),
            )
            conn.commit()
        finally:
            conn.close()

    def expire_overdue(self) -> int:
        """expires_at geçmiş PENDING talepleri EXPIRED yapar. Döner: etkilenen satır."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                UPDATE approval_requests SET status = 'EXPIRED'
                WHERE status = 'PENDING' AND expires_at IS NOT NULL AND expires_at < GETDATE()
            """)
            n = cursor.rowcount
            conn.commit()
            return n
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _row_to_dict(cursor, row) -> dict:
        cols = [c[0] for c in cursor.description]
        return ApprovalRepository._row_to_dict_cols(cols, row)

    @staticmethod
    def _row_to_dict_cols(cols: list[str], row) -> dict:
        d = dict(zip(cols, row))
        for k in ("created_at", "decided_at", "expires_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        for raw, parsed in (("filters_json", "filters"),
                            ("requested_params_json", "requested_params"),
                            ("result_json", "result")):
            if d.get(raw):
                try: d[parsed] = json.loads(d[raw])
                except Exception: d[parsed] = {}
            d.pop(raw, None)
        return d
