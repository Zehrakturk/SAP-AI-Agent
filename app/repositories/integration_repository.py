"""
IntegrationRepository — integrations + integration_params + integration_schemas
tablolarını okuyup IntegrationConfig DTO'sunu üretir.

Burası MSSQL şemasına bağımlı tek katman. service_type/auth_type/extra_config
kolonları henüz yoksa varsayılan değerlerle (SOAP/BASIC/{}) çalışır → geriye uyum.
"""

from __future__ import annotations

from app.services.db                                  import get_connection
from app.services.fetchers.models.integration_config   import (
    IntegrationConfig, IntegrationParam,
)
from app.services.fetchers.core.exceptions             import IntegrationNotFoundError


class IntegrationRepository:

    # ─────────────────────────────────────────────────────────────────────
    # Tek public okuma metodu — config + paramlar + schema bilgisi birlikte
    # ─────────────────────────────────────────────────────────────────────
    def get_with_params(self, integration_id: int) -> IntegrationConfig:
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            row, columns = self._read_integration_row(cursor, integration_id)
            if not row:
                raise IntegrationNotFoundError(
                    f"integration_id={integration_id} bulunamadı veya pasif."
                )

            row_dict = dict(zip(columns, row))
            params   = self._read_params(cursor, integration_id)
            target_table, schema_text = self._read_schema(cursor, integration_id)

            return IntegrationConfig.from_row(
                row_dict, params=params,
                target_table=target_table, schema_text=schema_text,
            )
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    def list_active(self, company: str | None = None) -> list[IntegrationConfig]:
        """
        Aktif (is_active=1) entegrasyonları döner.
        company verilirse (ve 'ALL' değilse) yalnız o firmanınkiler.
        """
        conn   = get_connection()
        cursor = conn.cursor()
        try:
            available_cols = self._available_columns(cursor, "integrations")
            select_cols    = ", ".join(f"[{c}]" for c in available_cols)
            where  = "WHERE is_active = 1"
            params : list = []
            if company and company != "ALL" and "company" in available_cols:
                where += " AND company = ?"
                params.append(company)
            cursor.execute(f"SELECT {select_cols} FROM integrations {where}", params)
            rows = cursor.fetchall()
            configs = []
            for r in rows:
                row_dict = dict(zip(available_cols, r))
                int_id   = int(row_dict["id"])
                params   = self._read_params(cursor, int_id)
                tt, st   = self._read_schema(cursor, int_id)
                configs.append(IntegrationConfig.from_row(
                    row_dict, params=params, target_table=tt, schema_text=st
                ))
            return configs
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────
    # İç yardımcılar
    # ─────────────────────────────────────────────────────────────────────
    def _available_columns(self, cursor, table_name: str) -> list[str]:
        """integrations tablosunda hangi kolonlar mevcut (yeni kolonlar yoksa geriye uyum)."""
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
            (table_name,),
        )
        return [r[0] for r in cursor.fetchall()]

    def _read_integration_row(self, cursor, integration_id: int):
        available = self._available_columns(cursor, "integrations")
        select_cols = ", ".join(f"[{c}]" for c in available)
        cursor.execute(
            f"SELECT {select_cols} FROM integrations WHERE id = ? AND is_active = 1",
            (integration_id,),
        )
        return cursor.fetchone(), available

    def _read_params(self, cursor, integration_id: int) -> list[IntegrationParam]:
        cursor.execute(
            "SELECT param_name, param_type, is_required, default_value, description "
            "FROM integration_params WHERE integration_id = ? ORDER BY id",
            (integration_id,),
        )
        return [
            IntegrationParam(
                param_name    = r[0],
                param_type    = r[1],
                is_required   = bool(r[2]) if r[2] is not None else False,
                default_value = r[3],
                description   = r[4],
            )
            for r in cursor.fetchall()
        ]

    def _read_schema(self, cursor, integration_id: int):
        cursor.execute(
            "SELECT target_table, schema_text FROM integration_schemas "
            "WHERE integration_id = ?",
            (integration_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None, None
        return row[0], row[1]
