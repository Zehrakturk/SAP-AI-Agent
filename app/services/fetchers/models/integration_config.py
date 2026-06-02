"""
IntegrationConfig — MSSQL'deki integrations + integration_params + integration_schemas
satırlarının birleşik, immutable temsili.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing      import Any


@dataclass(frozen=True)
class IntegrationParam:
    """integration_params tablosundaki bir kayıt."""
    param_name   : str
    param_type   : str | None = None
    is_required  : bool       = False
    default_value: str | None = None
    description  : str | None = None


@dataclass(frozen=True)
class IntegrationConfig:
    """
    integrations tablosundan okunan tam konfigürasyon (immutable).

    Eski/yeni kolonlar:
      Mevcut: id, name, description, wsdl_url, service_method, username, password, is_active
      Yeni  : service_type (SOAP/REST/ODATA/GRAPHQL), auth_type (BASIC/BEARER/OAUTH2/NONE),
              extra_config (JSON blob: base_url, headers, endpoint, query_template ...)
    """
    id            : int
    name          : str
    is_active     : bool
    service_type  : str                  = "SOAP"
    auth_type     : str                  = "BASIC"
    description   : str | None           = None
    wsdl_url      : str | None           = None      # SOAP için. REST'te base URL olabilir.
    service_method: str | None           = None
    username      : str | None           = None
    password      : str | None           = None      # BEARER tipinde token olarak da kullanılır
    extra_config  : dict                 = field(default_factory=dict)
    params        : list[IntegrationParam] = field(default_factory=list)
    target_table  : str | None           = None
    schema_text   : str | None           = None

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def from_row(row: dict, params: list[IntegrationParam] | None = None,
                 target_table: str | None = None,
                 schema_text: str | None = None) -> "IntegrationConfig":
        """
        MSSQL satır dict'ini IntegrationConfig'e çevirir.
        Yeni kolonlar (service_type, auth_type, extra_config) yoksa varsayılan kullanır.
        """
        extra_raw = row.get("extra_config")
        if isinstance(extra_raw, str) and extra_raw.strip():
            try:
                extra = json.loads(extra_raw)
            except json.JSONDecodeError:
                extra = {}
        elif isinstance(extra_raw, dict):
            extra = extra_raw
        else:
            extra = {}

        return IntegrationConfig(
            id            = int(row["id"]),
            name          = row.get("name") or "",
            is_active     = bool(row.get("is_active", 1)),
            service_type  = (row.get("service_type") or "SOAP").upper(),
            auth_type     = (row.get("auth_type")    or "BASIC").upper(),
            description   = row.get("description"),
            wsdl_url      = row.get("wsdl_url"),
            service_method= row.get("service_method"),
            username      = row.get("username"),
            password      = row.get("password"),
            extra_config  = extra,
            params        = params or [],
            target_table  = target_table,
            schema_text   = schema_text,
        )

    # ─────────────────────────────────────────────────────────────────────
    def get_endpoint(self) -> str | None:
        """
        SOAP için wsdl_url, REST için extra_config['base_url'] ya da wsdl_url fallback.
        """
        if self.service_type == "SOAP":
            return self.wsdl_url
        return self.extra_config.get("base_url") or self.wsdl_url

    def effective_target_table(self) -> str:
        """Hedef tablo adı — yoksa fallback."""
        return self.target_table or f"int_{self.id}_data"
