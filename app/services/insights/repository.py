"""
InsightsRepository — MSSQL'de insights tablosu yönetimi + CRUD.
Tablo yoksa otomatik oluşturulur.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from app.services.insights.models import InsightCard

from app.services.db import get_connection


class InsightsRepository:

    def __init__(self):
        self._ensured = False

    # ─────────────────────────────────────────────────────────────────────
    def _ensure_table(self, cursor):
        if self._ensured:
            return
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'insights')
            CREATE TABLE insights (
                id             INT IDENTITY(1,1) PRIMARY KEY,
                external_id    NVARCHAR(40) NOT NULL,
                insight_type   NVARCHAR(40),
                severity       NVARCHAR(20),
                title          NVARCHAR(500),
                summary        NVARCHAR(MAX),
                metric         NVARCHAR(100),
                delta_pct      FLOAT,
                payload_json   NVARCHAR(MAX),
                user_id        NVARCHAR(50),
                tags           NVARCHAR(500),
                drill_action   NVARCHAR(500),
                icon           NVARCHAR(20),
                color          NVARCHAR(20),
                generated_at   DATETIME DEFAULT GETDATE(),
                viewed_at      DATETIME,
                dismissed_at   DATETIME
            )
        """)
        self._ensured = True

    # ─────────────────────────────────────────────────────────────────────
    def save(self, card: "InsightCard") -> int:
        """Bir InsightCard'ı MSSQL'e kaydeder, eklenen satırın id'sini döner."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute("""
                INSERT INTO insights
                  (external_id, insight_type, severity, title, summary, metric,
                   delta_pct, payload_json, user_id, tags, drill_action, icon, color)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card._id, card.type, card.severity, card.title[:500],
                (card.summary or "")[:4000],
                card.metric, card.delta_pct,
                card.to_json(),
                card.user_id,
                ",".join(card.tags)[:500] if card.tags else None,
                (card.drill_down_question or "")[:500] or None,
                card.icon[:20], card.color[:20],
            ))
            row = cursor.fetchone()
            new_id = int(row[0]) if row and row[0] is not None else 0
            conn.commit()
            return new_id
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def list_active(self, user_id: str | None = None, limit: int = 20,
                    include_dismissed: bool = False) -> list[dict]:
        """
        Aktif insight'ları listeler. user_id verilirse:
          - O kullanıcıya özel + global insight'lar
          - Aksi halde sadece global
        """
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            where = ["1=1"]
            params: list = []

            if not include_dismissed:
                where.append("dismissed_at IS NULL")

            if user_id is None:
                where.append("user_id IS NULL")
            else:
                where.append("(user_id = ? OR user_id IS NULL)")
                params.append(user_id)

            # Son 7 günden eski olmayanlar
            where.append("generated_at >= ?")
            params.append(datetime.now() - timedelta(days=7))

            sql = f"""
                SELECT TOP {int(limit)}
                       id, external_id, insight_type, severity, title, summary,
                       metric, delta_pct, payload_json, user_id, tags,
                       drill_action, icon, color, generated_at, viewed_at
                FROM   insights
                WHERE  {' AND '.join(where)}
                ORDER  BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'warning'  THEN 2
                        WHEN 'info'     THEN 3
                        ELSE 4
                    END,
                    generated_at DESC
            """
            cursor.execute(sql, params)
            cols = [c[0] for c in cursor.description]
            rows = []
            for r in cursor.fetchall():
                d = dict(zip(cols, r))
                # payload_json -> dict
                if d.get("payload_json"):
                    try:
                        d["payload"] = json.loads(d["payload_json"])
                    except Exception:
                        d["payload"] = {}
                d.pop("payload_json", None)
                if isinstance(d.get("generated_at"), datetime):
                    d["generated_at"] = d["generated_at"].isoformat()
                if isinstance(d.get("viewed_at"), datetime):
                    d["viewed_at"] = d["viewed_at"].isoformat()
                rows.append(d)
            return rows
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def mark_viewed(self, insight_id: int) -> None:
        self._update_ts(insight_id, "viewed_at")

    def mark_dismissed(self, insight_id: int) -> None:
        self._update_ts(insight_id, "dismissed_at")

    def _update_ts(self, insight_id: int, col: str) -> None:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute(
                f"UPDATE insights SET {col} = GETDATE() WHERE id = ?",
                (insight_id,)
            )
            conn.commit()
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def clear_old(self, days: int = 30) -> int:
        """N günden eski insight'ları siler. Döner: silinen satır sayısı."""
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_table(cursor)
            cursor.execute(
                "DELETE FROM insights WHERE generated_at < ?",
                (datetime.now() - timedelta(days=days),)
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()
