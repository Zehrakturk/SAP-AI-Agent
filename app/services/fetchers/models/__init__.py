"""DTO / Value objects — IntegrationConfig, FetchContext."""

from app.services.fetchers.models.integration_config import IntegrationConfig, IntegrationParam
from app.services.fetchers.models.fetch_context     import FetchContext

__all__ = ["IntegrationConfig", "IntegrationParam", "FetchContext"]
