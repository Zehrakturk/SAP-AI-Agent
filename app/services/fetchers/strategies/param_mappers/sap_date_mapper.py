"""SAP tarih parametrelerini eşleyen mapper.

ISTART_DATE / IFINISH_DATE / I_BEGDA / I_ENDDA gibi yaygın SAP isimlerini
extracted['start_date'] / ['end_date'] değerlerine bağlar.
"""

from __future__ import annotations

from app.services.fetchers.strategies.param_mappers.base import AbstractParamMapper


class SapDateMapper(AbstractParamMapper):
    """
    SAP SOAP tarih parametre mapper'ı.

    Varsayılan format ISO: 'YYYY-MM-DD' (örn. '2026-05-01').
    Eski sistemler 'YYYYMMDD' ister — date_format='compact' verilirse o formatla gönderilir.
    """

    START_KEYWORDS  = ("START", "BEGIN", "BEGDA", "ISTART", "FROM")
    FINISH_KEYWORDS = ("END", "FINISH", "ENDDA", "IFINISH", "TO")

    def __init__(self, date_format: str = "iso"):
        # "iso" -> 2026-05-01,  "compact" -> 20260501
        self.date_format = (date_format or "iso").lower()

    def map(self, integration_params, extracted: dict) -> dict:
        result = {}

        start = self._format_date(extracted.get("start_date") or extracted.get("baslangic"))
        end   = self._format_date(extracted.get("end_date")   or extracted.get("bitis"))

        for p in integration_params:
            name  = (p.param_name or "").upper()
            ptype = (p.param_type or "").upper()
            is_date = "DATE" in ptype or "DATE" in name

            if is_date:
                if any(k in name for k in self.START_KEYWORDS) and start:
                    result[p.param_name] = start
                elif any(k in name for k in self.FINISH_KEYWORDS) and end:
                    result[p.param_name] = end
            else:
                # Tarih dışı → extracted'tan eşleşeni veya default'u kullan
                key_norm = p.param_name.lower()
                if key_norm in extracted:
                    result[p.param_name] = extracted[key_norm]
                elif p.default_value:
                    result[p.param_name] = p.default_value

        return result

    # ─────────────────────────────────────────────────────────────────────
    def _format_date(self, value):
        """Girdiyi ISO ('YYYY-MM-DD') veya compact ('YYYYMMDD') formata çevirir."""
        if not value:
            return None
        s = str(value).strip()
        clean = s.replace("-", "").replace("/", "").replace(".", "")
        if len(clean) != 8 or not clean.isdigit():
            return None
        if self.date_format == "compact":
            return clean
        # iso (default)
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
