"""SAP SOAP envelope normalize — ET_RETURN / ET_DATA / RETURN.item kalıbı."""

from __future__ import annotations
from typing import Any

from app.services.fetchers.strategies.normalizers.base import AbstractNormalizer


class SapEnvelopeNormalizer(AbstractNormalizer):
    """
    SAP SOAP yanıtlarındaki yaygın envelope'ları çözer:
      - ET_RETURN, ET_DATA, ET_TABLE, RETURN, DATA, TABLE → list[dict]
      - {key: {"item": [...]}} → [...]
      - Düz dict → [dict]
      - list → kayıt listesi (her eleman dict'e zorlanır)
    """

    ENVELOPE_KEYS = ("ET_RETURN", "ET_DATA", "ET_TABLE", "RETURN", "DATA", "TABLE")

    def normalize(self, raw: Any) -> list[dict]:
        if raw is None:
            return []

        # Liste → her elemanı dict'e zorla
        if isinstance(raw, list):
            return [self._to_dict(r) for r in raw]

        # Dict → bilinen envelope anahtarlarını dene
        if isinstance(raw, dict):
            for key in self.ENVELOPE_KEYS:
                table = raw.get(key)
                if table is None:
                    continue
                items = self._extract_items(table)
                if items:
                    return items

            # Envelope yoksa düz dict → tek satır
            return [raw]

        return []

    # ─────────────────────────────────────────────────────────────────────
    def _extract_items(self, table: Any) -> list[dict]:
        if isinstance(table, list):
            return [self._to_dict(r) for r in table]
        if isinstance(table, dict):
            items = table.get("item")
            if items is None:
                # Envelope ama içeride farklı yapı varsa, dict olarak tek satır
                return [table]
            if isinstance(items, dict):
                return [items]
            if isinstance(items, list):
                return [self._to_dict(r) for r in items]
        return []

    @staticmethod
    def _to_dict(rec: Any) -> dict:
        if isinstance(rec, dict):
            return rec
        if hasattr(rec, "__dict__"):
            return dict(rec.__dict__)
        return {"VALUE": rec}
