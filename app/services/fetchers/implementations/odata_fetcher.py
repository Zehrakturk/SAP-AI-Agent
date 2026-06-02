"""
ODataFetcher — SAP OData v2/v4 servisleri.
RestFetcher'ı genişletir, OData $filter / $select / $top parametrelerini
otomatik üretebilir.

@FetcherFactory.register("ODATA")
"""

from __future__ import annotations

from app.services.fetchers.core.factory       import FetcherFactory
from app.services.fetchers.implementations.rest_fetcher import RestFetcher
from app.services.fetchers.strategies.param_mappers     import AbstractParamMapper


class _ODataParamMapper(AbstractParamMapper):
    """
    Tarih aralığı + opsiyonel ek filtreleri OData $filter string'ine çevirir.

      extracted = {"start_date": "2026-04-01", "end_date": "2026-04-07"}
      extra_config.date_field = "CreatedAt"
      → {"$filter": "CreatedAt ge 2026-04-01 and CreatedAt le 2026-04-07"}
    """

    def __init__(self, date_field: str | None = None, extra_filter: str | None = None,
                 top: int | None = None, select: str | None = None):
        self.date_field   = date_field
        self.extra_filter = extra_filter
        self.top          = top
        self.select       = select

    def map(self, integration_params, extracted: dict) -> dict:
        result = {}
        start = extracted.get("start_date") or extracted.get("baslangic")
        end   = extracted.get("end_date")   or extracted.get("bitis")

        filters = []
        if self.date_field and start:
            filters.append(f"{self.date_field} ge {start}")
        if self.date_field and end:
            filters.append(f"{self.date_field} le {end}")
        if self.extra_filter:
            filters.append(self.extra_filter)

        if filters:
            result["$filter"] = " and ".join(filters)
        if self.top:
            result["$top"] = self.top
        if self.select:
            result["$select"] = self.select

        # Tanımlı integration_params'ı da ekle
        for p in integration_params:
            key = p.param_name.lower()
            if key in extracted:
                result[p.param_name] = extracted[key]
            elif p.default_value and p.param_name not in result:
                result[p.param_name] = p.default_value

        return result


@FetcherFactory.register("ODATA")
class ODataFetcher(RestFetcher):
    """
    OData fetcher — RestFetcher'ın özelleşmiş versiyonu.

    extra_config'te beklenenler:
      base_url       : OData endpoint (entity set'i dahil)
      date_field     : Tarih filtresi için OData field adı
      extra_filter   : Ek $filter clause (opsiyonel)
      top, select    : OData query option'ları (opsiyonel)
    """

    def _create_param_mapper(self):
        extra = self.config.extra_config or {}
        return _ODataParamMapper(
            date_field   = extra.get("date_field"),
            extra_filter = extra.get("extra_filter"),
            top          = extra.get("top"),
            select       = extra.get("select"),
        )

    def _create_normalizer(self):
        # OData v2: {"d":{"results":[...]}}, v4: {"value":[...]} — RestJson her ikisini de tanır
        from app.services.fetchers.strategies.normalizers import RestJsonNormalizer
        return RestJsonNormalizer()
