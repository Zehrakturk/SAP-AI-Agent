"""Düz JSON REST yanıtlarını normalize eden strateji."""

from __future__ import annotations
from typing import Any

from app.services.fetchers.strategies.normalizers.base import AbstractNormalizer


class RestJsonNormalizer(AbstractNormalizer):
    """
    Yaygın REST yanıt kalıpları:
      - JSON Array            → [...]
      - {"data": [...]}       → data
      - {"items": [...]}      → items
      - {"results": [...]}    → results
      - {"value": [...]}      → value (OData v3/v4)
      - {"d": {"results":[...]}} → d.results (OData v2)
      - Düz obje              → [obj]

    `data_key` parametresi verilirse o anahtardan çıkartır.
    """

    DEFAULT_KEYS = ("data", "items", "results", "value", "records", "rows", "list")

    def __init__(self, data_key: str | None = None):
        self.data_key = data_key

    def normalize(self, raw: Any) -> list[dict]:
        if raw is None:
            return []

        if isinstance(raw, list):
            return [self._to_dict(r) for r in raw]

        if isinstance(raw, dict):
            # 1) Açıkça verilmiş data_key
            if self.data_key:
                node = self._dig(raw, self.data_key)
                if isinstance(node, list):
                    return [self._to_dict(r) for r in node]
                if isinstance(node, dict):
                    return [node]

            # 2) OData v2: {"d": {"results": [...]}}
            d_node = raw.get("d")
            if isinstance(d_node, dict) and isinstance(d_node.get("results"), list):
                return [self._to_dict(r) for r in d_node["results"]]

            # 3) Yaygın anahtarlar
            for key in self.DEFAULT_KEYS:
                node = raw.get(key)
                if isinstance(node, list):
                    return [self._to_dict(r) for r in node]

            # 4) Düz dict → tek kayıt
            return [raw]

        return []

    @staticmethod
    def _dig(obj: Any, dotted: str) -> Any:
        """`data.items` gibi nokta ile ayrılmış path destekler."""
        for part in dotted.split("."):
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj

    @staticmethod
    def _to_dict(rec: Any) -> dict:
        return rec if isinstance(rec, dict) else {"VALUE": rec}
