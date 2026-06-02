"""
RestFetcher — JSON REST servisleri (GET/POST).
@FetcherFactory.register("REST")
"""

from __future__ import annotations

import requests

from app.services.fetchers.core.base       import AbstractFetcher
from app.services.fetchers.core.factory    import FetcherFactory
from app.services.fetchers.core.result     import FetchResult
from app.services.fetchers.core.exceptions import FetcherError, ResponseError, AuthError

from app.services.fetchers.strategies.auth                 import create_auth_strategy
from app.services.fetchers.strategies.normalizers          import RestJsonNormalizer
from app.services.fetchers.strategies.param_mappers        import RestQueryMapper, TemplateMapper


@FetcherFactory.register("REST")
class RestFetcher(AbstractFetcher):
    """
    Genel REST fetcher.

    extra_config (integrations.extra_config JSON):
      base_url      : Tam endpoint (yoksa wsdl_url alanı kullanılır)
      http_method   : "GET" | "POST"  (default GET)
      data_key      : Response içinde liste'nin durduğu anahtar (RestJsonNormalizer'a)
      param_in      : "query" | "body" (default query, GET için)
      headers       : Ek HTTP header dict
      param_template: TemplateMapper için body/query şablonu
    """

    # ─────────────────────────────────────────────────────────────────────
    def _create_auth_strategy(self):
        return create_auth_strategy(
            self.config.auth_type or "BEARER",
            self.config.username, self.config.password,
            self.config.extra_config,
        )

    def _create_normalizer(self):
        data_key = (self.config.extra_config or {}).get("data_key")
        return RestJsonNormalizer(data_key=data_key)

    def _create_param_mapper(self):
        template = (self.config.extra_config or {}).get("param_template")
        if template:
            return TemplateMapper(template=template)
        return RestQueryMapper()

    # ─────────────────────────────────────────────────────────────────────
    def fetch(self, context) -> FetchResult:
        self.validate(context)

        url = self.config.get_endpoint()
        if not url:
            raise FetcherError(f"REST endpoint tanımsız: {self.config.name}")

        extra        = self.config.extra_config or {}
        http_method  = (extra.get("http_method") or "GET").upper()
        param_in     = (extra.get("param_in") or ("body" if http_method == "POST" else "query")).lower()

        headers = {"Accept": "application/json"}
        headers.update(self.auth.build_headers())
        headers.update(extra.get("headers") or {})

        call_params = self.param_mapper.map(self.config.params, context.extracted)
        print(f"[REST] {http_method} {url}  params={call_params}")

        try:
            if http_method == "POST":
                if param_in == "query":
                    resp = requests.post(url, headers=headers, params=call_params, timeout=60)
                else:
                    headers.setdefault("Content-Type", "application/json")
                    resp = requests.post(url, headers=headers, json=call_params, timeout=60)
            else:
                resp = requests.get(url, headers=headers, params=call_params, timeout=60)
        except requests.RequestException as e:
            raise ResponseError(f"REST çağrı hatası: {e}") from e

        if resp.status_code == 401:
            raise AuthError(f"401 Unauthorized — {self.config.name}")
        if not resp.ok:
            raise ResponseError(
                f"REST HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            payload = resp.json()
        except ValueError as e:
            raise ResponseError(f"Geçersiz JSON yanıt: {e}") from e

        records = self.normalizer.normalize(payload)

        return FetchResult(
            records        = records,
            call_params    = call_params,
            integration_id = self.config.id,
            raw_response   = payload,
        )
