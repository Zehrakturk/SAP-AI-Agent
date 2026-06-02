"""
Insights modülünün veri yapıları.
InsightCard, Hypothesis, DetectorContext.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime    import datetime
from typing      import Any


@dataclass
class Hypothesis:
    """Bir içgörünün altındaki kök-sebep önerisi."""
    text         : str
    confidence   : float = 0.5
    evidence_sql : str | None = None
    metric_delta : float | None = None
    tags         : list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InsightCard:
    """
    Dashboard'da gösterilecek tek bir proaktif içgörü.

    type      : trend_change | anomaly | top_mover | stuck_record | correlation
    severity  : info | warning | critical
    """
    type       : str
    severity   : str
    title      : str
    summary    : str = ""                         # Kısa Türkçe açıklama
    metric     : str | None = None
    current    : float | None = None
    previous   : float | None = None
    delta_pct  : float | None = None
    timeframe  : str | None = None                # "2026-05-25 → 2026-05-31"
    comparison : str | None = None
    hypotheses : list[Hypothesis] = field(default_factory=list)
    drill_down_question : str | None = None
    tags                : list[str] = field(default_factory=list)
    icon                : str = "💡"
    color               : str = "blue"
    user_id             : str | None = None        # None = global

    # Yardımcı
    _id : str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # ─────────────────────────────────────────────────────────────────────
    def to_payload(self) -> dict:
        """payload_json kolonuna yazılacak tam içerik."""
        d = asdict(self)
        d["hypotheses"] = [h if isinstance(h, dict) else h.to_dict()
                           for h in self.hypotheses]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False, default=str)


@dataclass
class DetectorContext:
    """
    Bir detector'a verilen runtime context.
    Detector'lar bu nesneden tarih aralıklarını ve hedef integration'ı alır.
    """
    today       : datetime
    user_id     : str | None = None
    integration_ids : list[int] = field(default_factory=list)   # boş = tüm aktifler
    extra        : dict[str, Any] = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def now(user_id: str | None = None, integration_ids: list[int] | None = None) -> "DetectorContext":
        return DetectorContext(
            today           = datetime.now(),
            user_id         = user_id,
            integration_ids = integration_ids or [],
        )
