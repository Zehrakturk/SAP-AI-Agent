"""
Concrete insight detector'ları.

Bu modülü import etmek tüm detector'ların REGISTRY'ye kaydedilmesini tetikler.
Yeni detector eklemek: bu klasöre dosya koy + @register + buraya import ekle.
"""

from app.services.insights.detectors.trend_change    import TrendChangeDetector    # noqa: F401
from app.services.insights.detectors.top_mover       import TopMoverDetector       # noqa: F401
from app.services.insights.detectors.stuck_record    import StuckRecordDetector    # noqa: F401
from app.services.insights.detectors.anomaly         import AnomalyDetector        # noqa: F401
from app.services.insights.detectors.correlation     import CorrelationDetector    # noqa: F401

__all__ = [
    "TrendChangeDetector",
    "TopMoverDetector",
    "StuckRecordDetector",
    "AnomalyDetector",
    "CorrelationDetector",
]
