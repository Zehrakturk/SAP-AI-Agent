"""FetchResult — fetcher dönüş tipi."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing      import Any


@dataclass
class FetchResult:
    """
    Bir fetcher çağrısının sonucu.

    records         : Normalize edilmiş kayıt listesi (list[dict])
    call_params     : Servise gönderilen son parametre seti (debug/log için)
    integration_id  : Kaynak entegrasyon id'si
    raw_response    : Ham yanıt (opsiyonel, debug için)
    """
    records       : list[dict]
    call_params   : dict
    integration_id: int
    raw_response  : Any = field(default=None, repr=False)

    @property
    def count(self) -> int:
        return len(self.records)

    def __bool__(self) -> bool:
        return bool(self.records)
