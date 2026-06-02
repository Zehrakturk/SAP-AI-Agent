"""REST query string mapper — ISO tarihleri + diğer parametreleri eşler."""

from __future__ import annotations

from app.services.fetchers.strategies.param_mappers.base import AbstractParamMapper


class RestQueryMapper(AbstractParamMapper):
    """
    REST için tarihler ISO formatında ('YYYY-MM-DD') kalır.
    Param adı için yaygın anahtarlar:
      start_date / from / begin / startDate / dateFrom → start_date
      end_date   / to   / finish / endDate   / dateTo  → end_date
    """

    START_KEYWORDS  = ("START", "BEGIN", "FROM")
    FINISH_KEYWORDS = ("END", "FINISH", "TO")

    def map(self, integration_params, extracted: dict) -> dict:
        result = {}

        start = self._to_iso(extracted.get("start_date") or extracted.get("baslangic"))
        end   = self._to_iso(extracted.get("end_date")   or extracted.get("bitis"))

        for p in integration_params:
            name      = (p.param_name or "").upper()
            ptype     = (p.param_type or "").upper()
            is_date   = "DATE" in ptype or "DATE" in name

            if is_date:
                if any(k in name for k in self.START_KEYWORDS) and start:
                    result[p.param_name] = start
                elif any(k in name for k in self.FINISH_KEYWORDS) and end:
                    result[p.param_name] = end
                else:
                    # Tarih ama isim eşleşmedi → default varsa kullan
                    if p.default_value:
                        result[p.param_name] = p.default_value
            else:
                key_norm = p.param_name.lower()
                if key_norm in extracted:
                    result[p.param_name] = extracted[key_norm]
                elif p.default_value:
                    result[p.param_name] = p.default_value

        return result

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _to_iso(value):
        if not value:
            return None
        s = str(value).strip()
        # YYYYMMDD → YYYY-MM-DD
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return s if len(s) >= 8 else None
