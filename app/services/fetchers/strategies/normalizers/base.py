"""AbstractNormalizer — ham servis yanıtını list[dict]'e çeviren stratejilerin temel sınıfı."""

from __future__ import annotations
from abc        import ABC, abstractmethod
from typing     import Any


class AbstractNormalizer(ABC):
    @abstractmethod
    def normalize(self, raw: Any) -> list[dict]:
        """
        Ham yanıtı normalize edilmiş kayıt listesine çevirir.
        Veri bulunmadıysa boş liste döner — None DÖNDÜRMEZ.
        """
        raise NotImplementedError
