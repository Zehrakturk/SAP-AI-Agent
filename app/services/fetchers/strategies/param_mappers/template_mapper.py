"""
Template tabanlı parametre mapper.

GraphQL ve karmaşık REST'ler için: extra_config içindeki query template'ini
{baslangic}, {bitis}, {customer_id} gibi placeholder'larla doldurur.
"""

from __future__ import annotations

import re
from app.services.fetchers.strategies.param_mappers.base import AbstractParamMapper


class TemplateMapper(AbstractParamMapper):
    """
    extra_config['param_template'] içindeki {placeholder}'ları
    extracted dict'inden ve integration_params default_value'larından doldurur.

    Örnek:
      template = {"from": "{start_date}", "to": "{end_date}", "limit": "100"}
      extracted = {"start_date": "2026-04-01", "end_date": "2026-04-07"}
      → {"from": "2026-04-01", "to": "2026-04-07", "limit": "100"}
    """

    PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

    def __init__(self, template: dict | None = None):
        self.template = template or {}

    def map(self, integration_params, extracted: dict) -> dict:
        # Defaults — integration_params'tan
        sources = {p.param_name: p.default_value for p in integration_params if p.default_value}
        sources.update(extracted)

        if not self.template:
            # Template yoksa düz dict — extracted'ı param adlarıyla eşle
            return {p.param_name: extracted.get(p.param_name) or p.default_value
                    for p in integration_params
                    if extracted.get(p.param_name) or p.default_value}

        result = {}
        for key, raw_val in self.template.items():
            if isinstance(raw_val, str):
                result[key] = self.PLACEHOLDER_RE.sub(
                    lambda m: str(sources.get(m.group(1), "")), raw_val
                )
            else:
                result[key] = raw_val
        return result
