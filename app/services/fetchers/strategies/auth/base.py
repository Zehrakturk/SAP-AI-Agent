"""AbstractAuthStrategy — auth stratejilerinin temel arayüzü."""

from __future__ import annotations
from abc        import ABC, abstractmethod
from typing     import Any


class AbstractAuthStrategy(ABC):
    """
    Hem SOAP (requests.Session) hem REST (header dict) için
    auth bilgisini sağlayabilen sözleşme.
    """

    @abstractmethod
    def apply_to_session(self, session: Any) -> Any:
        """SOAP/zeep: requests.Session üzerine auth uygula, session'ı döner."""
        raise NotImplementedError

    @abstractmethod
    def build_headers(self) -> dict:
        """REST: HTTP header dict döner (Authorization vb.)."""
        raise NotImplementedError
