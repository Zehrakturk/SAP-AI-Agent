"""Core abstractions: AbstractFetcher, FetcherFactory, exceptions, FetchResult."""

from app.services.fetchers.core.base       import AbstractFetcher
from app.services.fetchers.core.factory    import FetcherFactory
from app.services.fetchers.core.exceptions import (
    FetcherError, AuthError, ResponseError, ParamMappingError,
)
from app.services.fetchers.core.result     import FetchResult

__all__ = [
    "AbstractFetcher", "FetcherFactory",
    "FetcherError", "AuthError", "ResponseError", "ParamMappingError",
    "FetchResult",
]
