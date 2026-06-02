"""
SoapFetcher — SAP/Zeep tabanlı SOAP servisleri.
@FetcherFactory.register("SOAP")
"""

from __future__ import annotations

from requests        import Session
from zeep            import Client
from zeep.helpers    import serialize_object
from zeep.transports import Transport

from app.services.fetchers.core.base       import AbstractFetcher
from app.services.fetchers.core.factory    import FetcherFactory
from app.services.fetchers.core.result     import FetchResult
from app.services.fetchers.core.exceptions import FetcherError, ResponseError

from app.services.fetchers.strategies.auth                 import create_auth_strategy
from app.services.fetchers.strategies.normalizers          import SapEnvelopeNormalizer
from app.services.fetchers.strategies.param_mappers        import SapDateMapper


@FetcherFactory.register("SOAP")
class SoapFetcher(AbstractFetcher):
    """SOAP/WSDL servisleri — Zeep istemcisi."""

    # ─────────────────────────────────────────────────────────────────────
    def _create_auth_strategy(self):
        return create_auth_strategy(
            self.config.auth_type or "BASIC",
            self.config.username, self.config.password,
            self.config.extra_config,
        )

    def _create_normalizer(self):
        return SapEnvelopeNormalizer()

    def _create_param_mapper(self):
        # extra_config.date_format ile override edilebilir: "iso" (default) | "compact"
        fmt = (self.config.extra_config or {}).get("date_format", "iso")
        return SapDateMapper(date_format=fmt)

    # ─────────────────────────────────────────────────────────────────────
    def fetch(self, context) -> FetchResult:
        self.validate(context)

        if not self.config.service_method:
            raise FetcherError(f"service_method tanımsız: {self.config.name}")

        session = self.auth.apply_to_session(Session())
        client  = Client(
            wsdl=self.config.wsdl_url,
            transport=Transport(session=session, timeout=60),
        )

        call_params = self.param_mapper.map(self.config.params, context.extracted)
        print(f"[SOAP] {self.config.name} ← {self.config.service_method}({call_params})")

        try:
            method   = getattr(client.service, self.config.service_method)
            raw_resp = method(**call_params)
        except AttributeError:
            raise FetcherError(
                f"WSDL'de '{self.config.service_method}' metodu bulunamadı."
            )
        except Exception as e:
            raise ResponseError(f"SOAP çağrı hatası: {e}") from e

        raw      = serialize_object(raw_resp)
        if isinstance(raw, dict):
            raw = dict(raw)
        elif hasattr(raw, "__dict__"):
            raw = dict(raw.__dict__)

        records = self.normalizer.normalize(raw)

        return FetchResult(
            records        = records,
            call_params    = call_params,
            integration_id = self.config.id,
            raw_response   = raw,
        )
