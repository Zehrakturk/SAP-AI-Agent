"""AbstractParamMapper — parametre eşleme stratejilerinin sözleşmesi."""

from __future__ import annotations
from abc        import ABC, abstractmethod
from typing     import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.fetchers.models.integration_config import IntegrationParam


class AbstractParamMapper(ABC):
    @abstractmethod
    def map(self, integration_params: "list[IntegrationParam]",
            extracted: dict) -> dict:
        """
        integration_params : MSSQL integration_params satırları (DTO)
        extracted          : Kullanıcı/intent parametreleri
                             (start_date, end_date, customer_id, ...)

        Döner: servis çağrısı için kullanılacak final parametre dict'i.
        """
        raise NotImplementedError
