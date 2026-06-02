"""
FetchContext — bir fetch çağrısının runtime girdileri.
Param hash burada hesaplanır (cache anahtarı).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class FetchContext:
    """
    Bir fetch çağrısı için runtime parametreleri.

    extracted: intent_parser veya kullanıcıdan gelen ham parametreler
               (start_date, end_date, customer_id, ...)
    extras   : protokol-spesifik ek bağlam (headers override, vb.)
    """
    extracted: dict = field(default_factory=dict)
    extras   : dict = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def from_extracted(extracted: dict | None) -> "FetchContext":
        return FetchContext(extracted=dict(extracted or {}))

    # ─────────────────────────────────────────────────────────────────────
    def param_hash(self, integration_id: int, call_params: dict | None = None) -> str:
        """
        Cache anahtarı. integration_id + parametreler birlikte hash'lenir.
        call_params verilmezse extracted kullanılır.
        """
        params = call_params if call_params is not None else self.extracted
        raw = json.dumps({"id": integration_id, **params}, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:16]
