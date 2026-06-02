"""
AuditRepository — append-only audit_log.

Her durum geçişi (kim / ne zaman / önce-sonra) buraya yazılır.
Asla UPDATE/DELETE yapılmaz — compliance için değişmez kayıt.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.services.db import get_connection


class AuditRepository:

    _ensured = False   # process ömrü boyunca tek sefer

    def _ensure_table(self, cursor) -> None:
        if AuditRepository._ensured:
            return
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'audit_log')
            CREATE TABLE audit_log (
                id          INT IDENTITY(1,1) PRIMARY KEY,
                entity_type NVARCHAR(40),
                entity_id   INT,
                action      NVARCHAR(60),
                actor       NVARCHAR(50),
                detail_json NVARCHAR(MAX),
                created_at  DATETIME DEFAULT GETDATE()
            )
        """)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_audit_entity')
            CREATE INDEX ix_audit_entity ON audit_log (entity_type, entity_id)
        """)
        AuditRepository._ensured = True

    # ─────────────────────────────────────────────────────────────────────
    def log(self, entity_type: str, entity_id: int, action: str,
            actor: str = "system", detail: dict | None = None) -> None:
        """Tek bir audit kaydı ekler. Hiç patlamamalı — patlarsa sessizce yutar."""
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            self._ensure_table(cursor)
            cursor.execute(
                "INSERT INTO audit_log (entity_type, entity_id, action, actor, detail_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (entity_type, int(entity_id), action, (actor or "system")[:50],
                 json.dumps(detail or {}, ensure_ascii=False, default=str)),
            )
            conn.commit()
        except Exception as e:
            print(f"[AUDIT] Kayıt başarısız ({entity_type}#{entity_id} {action}): {e}")
        finally:
            try: conn.close()
            except Exception: pass

    # ─────────────────────────────────────────────────────────────────────
    def list_for(self, entity_type: str, entity_id: int) -> list[dict]:
        """Bir varlığın tüm audit geçmişini kronolojik döner."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            conn.commit()
            cursor.execute(
                "SELECT action, actor, detail_json, created_at FROM audit_log "
                "WHERE entity_type = ? AND entity_id = ? ORDER BY id ASC",
                (entity_type, int(entity_id)),
            )
            out = []
            for action, actor, detail_json, created_at in cursor.fetchall():
                d = {"action": action, "actor": actor}
                if detail_json:
                    try: d["detail"] = json.loads(detail_json)
                    except Exception: d["detail"] = {}
                if isinstance(created_at, datetime):
                    d["created_at"] = created_at.isoformat()
                out.append(d)
            return out
        finally:
            conn.close()
