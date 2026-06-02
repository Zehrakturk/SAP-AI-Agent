"""
FetchLogger — fetch_log tablosunu yönetir.
Aynı (integration_id, param_hash) için cache hit kontrolü sağlar.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.fetchers.models.fetch_context import FetchContext

from app.services.db import get_connection


class FetchLogger:

    def __init__(self):
        self._ensured = False

    # ─────────────────────────────────────────────────────────────────────
    def _ensure_table(self, cursor):
        if self._ensured:
            return
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'fetch_log')
            CREATE TABLE fetch_log (
                id             INT IDENTITY(1,1) PRIMARY KEY,
                integration_id INT NOT NULL,
                param_hash     NVARCHAR(20)  NOT NULL,
                params_json    NVARCHAR(MAX),
                rows_written   INT DEFAULT 0,
                target_table   NVARCHAR(128),
                fetched_at     DATETIME DEFAULT GETDATE(),
                UNIQUE(integration_id, param_hash)
            )
        """)
        # target_table kolonu yoksa ekle (eski tablo yapısıyla uyumluluk)
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'fetch_log' AND COLUMN_NAME = 'target_table'
            )
            ALTER TABLE fetch_log ADD target_table NVARCHAR(128)
        """)
        self._ensured = True

    # ─────────────────────────────────────────────────────────────────────
    def is_already_fetched(self, integration_id: int, context: "FetchContext",
                           call_params: dict | None = None) -> bool:
        p_hash = context.param_hash(integration_id, call_params)
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute(
                "SELECT 1 FROM fetch_log WHERE integration_id = ? AND param_hash = ?",
                (integration_id, p_hash),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def get_cached_result(self, integration_id: int, context: "FetchContext",
                          call_params: dict | None = None) -> dict:
        p_hash = context.param_hash(integration_id, call_params)
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT rows_written, target_table FROM fetch_log "
                "WHERE integration_id = ? AND param_hash = ?",
                (integration_id, p_hash),
            )
            row = cursor.fetchone()
            if not row:
                return {"status": "cached", "rows_written": 0, "target_table": ""}
            return {
                "status"      : "cached",
                "rows_written": int(row[0] or 0),
                "target_table": row[1] or "",
                "message"     : "Bu parametreler için veri zaten çekilmiş.",
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def record(self, integration_id: int, context: "FetchContext",
               rows_written: int, target_table: str,
               call_params: dict | None = None) -> None:
        params = call_params if call_params is not None else context.extracted
        p_hash = context.param_hash(integration_id, call_params)

        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                MERGE fetch_log AS target
                USING (VALUES (?, ?, ?, ?, ?)) AS src
                    (integration_id, param_hash, params_json, rows_written, target_table)
                ON target.integration_id = src.integration_id
                   AND target.param_hash = src.param_hash
                WHEN MATCHED THEN
                    UPDATE SET rows_written = src.rows_written,
                               target_table = src.target_table,
                               fetched_at   = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (integration_id, param_hash, params_json, rows_written, target_table)
                    VALUES (src.integration_id, src.param_hash, src.params_json,
                            src.rows_written, src.target_table);
            """, (integration_id, p_hash,
                  json.dumps(params, default=str), rows_written, target_table))
            conn.commit()
        finally:
            conn.close()
