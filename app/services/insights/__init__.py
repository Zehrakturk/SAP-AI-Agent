"""
app/services/insights/

Proaktif içgörü motoru. Kullanıcı sormadan önce veriden anomali/trend/korelasyon
yakalar ve insight kartı üretir.

Public API:
    generate_insights(user_id=None) -> list[InsightCard]
    InsightDetectorFactory          — registry-tabanlı detector kayıt sistemi
"""

# Concrete detector'ların import'u — @register decorator REGISTRY'yi doldurur
from app.services.insights.detectors import *  # noqa: F401,F403

from app.services.insights.runner          import generate_insights, generate_for_user
from app.services.insights.factory         import InsightDetectorFactory

__all__ = [
    "generate_insights", "generate_for_user", "InsightDetectorFactory",
]
