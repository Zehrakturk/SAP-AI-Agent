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
            raw_resp = self._invoke(client, self.config.service_method, call_params)
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
        return self._build_result(raw, call_params)

    # ─────────────────────────────────────────────────────────────────────
    def _invoke(self, client, method_name: str, call_params: dict):
        """
        Operasyonu çağırır. Önce varsayılan service'i dener; bazı SAP WSDL'leri
        (özellikle ?wsdl ile alınanlar) <wsdl:service> içermez → 'no default service'
        hatası. Bu durumda WSDL'deki BINDING + endpoint adresi ile AÇIKÇA bağlanır.
        """
        # Operasyon adı toleransı: kullanıcı yanlışlıkla PORT/binding adını ('..._WS')
        # girmiş olabilir → gerçek operasyon genelde '_WS' eki olmayan halidir.
        candidates = [method_name]
        if method_name.endswith("_WS"):
            candidates.append(method_name[:-3])

        def _try_default():
            last = None
            for name in candidates:
                try:
                    op = getattr(client.service, name)
                except AttributeError as ae:
                    last = ae
                    continue
                if name != method_name:
                    print(f"[SOAP] '{method_name}' bulunamadı → '{name}' kullanılıyor")
                return op(**call_params)
            raise last or AttributeError(method_name)

        try:
            return _try_default()
        except Exception as e:
            if "no default service" not in str(e).lower():
                raise
            # Fallback: binding + adres ile servis oluştur
            address = (self.config.extra_config or {}).get("endpoint") \
                or (self.config.wsdl_url or "").split("?")[0]
            bindings = list(client.wsdl.bindings.keys())
            if not bindings:
                raise
            # SOAP 1.1 binding'i tercih et (soap12 olanı ele); mümkünse method adıyla eşleş
            def _score(qn):
                s = str(qn).lower()
                return (0 if "soap12" in s else 1) + (1 if method_name.lower() in s else 0)
            binding_qname = sorted(bindings, key=_score, reverse=True)[0]
            print(f"[SOAP] 'no default service' → binding ile bağlanılıyor: "
                  f"{binding_qname} @ {address}")
            service = client.create_service(binding_qname, address)
            last = None
            for name in candidates:
                try:
                    return getattr(service, name)(**call_params)
                except AttributeError as ae:
                    last = ae
            raise last or AttributeError(method_name)

    def _build_result(self, raw, call_params) -> FetchResult:

        records = self.normalizer.normalize(raw)

        return FetchResult(
            records        = records,
            call_params    = call_params,
            integration_id = self.config.id,
            raw_response   = raw,
        )
