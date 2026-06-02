"""
AbstractInsightDetector — tüm detector'ların uyması zorunlu sözleşme.
"""

from __future__ import annotations

from abc    import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.insights.models import InsightCard, DetectorContext


class AbstractInsightDetector(ABC):
    """
    Bir detector tek bir tür içgörü üretir (trend_change, anomaly vb.).
    `@InsightDetectorFactory.register("name")` ile kaydedilir.
    """

    DETECTOR_NAME: str = ""

    @abstractmethod
    def detect(self, context: "DetectorContext") -> list["InsightCard"]:
        """
        Veriyi tarayıp içgörü kartlarını döner.
        Boş liste = bu detector için kayda değer bulgu yok.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.DETECTOR_NAME}>"
