"""Response normalize stratejileri — ham servis cevabını list[dict]'e çevirir."""

from app.services.fetchers.strategies.normalizers.base         import AbstractNormalizer
from app.services.fetchers.strategies.normalizers.sap_envelope import SapEnvelopeNormalizer
from app.services.fetchers.strategies.normalizers.rest_json    import RestJsonNormalizer

__all__ = ["AbstractNormalizer", "SapEnvelopeNormalizer", "RestJsonNormalizer"]
