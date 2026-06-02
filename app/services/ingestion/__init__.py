"""
app/services/ingestion/ — Human-in-the-loop Dynamic Data Integration.

Eksik veri tespit edilince otomatik çekmek yerine admin onayına bağlı,
kuyruğa alınan, izlenebilir bir veri çekme süreci kurar.

Public API:
    detect_gap(...)             -> GapResult | None
    ApprovalService             -> create / approve / reject (state machine)
    process_pending_jobs()      -> APScheduler worker tick
"""

from app.services.ingestion.models           import (
    ApprovalStatus, JobStatus, AuditAction, GapResult, ApprovalRequest,
)
from app.services.ingestion.gap_detector      import detect_gap
from app.services.ingestion.approval_service  import ApprovalService
from app.services.ingestion.job_worker        import process_pending_jobs

__all__ = [
    "ApprovalStatus", "JobStatus", "AuditAction", "GapResult", "ApprovalRequest",
    "detect_gap", "ApprovalService", "process_pending_jobs",
]
