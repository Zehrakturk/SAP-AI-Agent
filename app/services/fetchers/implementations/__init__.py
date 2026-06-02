"""
Concrete fetcher implementations.

Bu modülün import edilmesi, her concrete fetcher'ın @FetcherFactory.register
decorator'ını tetikler — REGISTRY otomatik dolar.

Yeni protokol eklemek için: bu klasöre yeni dosya koy + register et + buraya import ekle.
"""

from app.services.fetchers.implementations.soap_fetcher    import SoapFetcher    # noqa: F401
from app.services.fetchers.implementations.rest_fetcher    import RestFetcher    # noqa: F401
from app.services.fetchers.implementations.odata_fetcher   import ODataFetcher   # noqa: F401

__all__ = ["SoapFetcher", "RestFetcher", "ODataFetcher"]
