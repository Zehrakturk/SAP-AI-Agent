"""
app/services/ingestion/ — Human-in-the-loop Dynamic Data Integration.

models.py — durum enum'ları ve veri yapıları.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime    import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Durum sabitleri (string enum — MSSQL NVARCHAR kolonlarıyla birebir)
# ─────────────────────────────────────────────────────────────────────────────

class ApprovalStatus:
    PENDING   = "PENDING"
    APPROVED  = "APPROVED"
    REJECTED  = "REJECTED"
    EXPIRED   = "EXPIRED"
    ALL       = (PENDING, APPROVED, REJECTED, EXPIRED)


class JobStatus:
    QUEUED    = "QUEUED"
    RUNNING   = "RUNNING"
    FETCHING  = "FETCHING"
    INDEXING  = "INDEXING"
    RERUNNING = "RERUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    # Aktif (worker'ın ilgilendiği) durumlar
    ACTIVE    = (RUNNING, FETCHING, INDEXING, RERUNNING)


class AuditAction:
    CREATED      = "CREATED"
    APPROVED     = "APPROVED"
    REJECTED     = "REJECTED"
    EXPIRED      = "EXPIRED"
    JOB_QUEUED   = "JOB_QUEUED"
    JOB_CLAIMED  = "JOB_CLAIMED"
    FETCH_DONE   = "FETCH_DONE"
    INDEXED      = "INDEXED"
    RERUN        = "RERUN"
    COMPLETED    = "COMPLETED"
    FAILED       = "FAILED"
    RETRY        = "RETRY"
    STALE_RECLAIM = "STALE_RECLAIM"


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: dedup hash
# ─────────────────────────────────────────────────────────────────────────────

def compute_request_hash(integration_id: int, params: dict, question: str) -> str:
    """
    Aynı talebi (entegrasyon + parametre + normalize soru) tek bir approval'a
    indirger. param_hash mantığıyla uyumlu — sıralı JSON.
    """
    norm_q = " ".join((question or "").lower().split())
    payload = json.dumps(
        {"i": integration_id, "p": params or {}, "q": norm_q},
        sort_keys=True, default=str,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass'lar
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GapResult:
    """gap_detector çıktısı — eksik veri tespit edildiğinde."""
    integration_id   : int
    integration_name : str
    params           : dict                  # {start_date, end_date, ...}
    reason           : str

    def to_dict(self) -> dict:
        return {
            "integration_id"  : self.integration_id,
            "integration_name": self.integration_name,
            "params"          : self.params,
            "reason"          : self.reason,
        }


@dataclass
class ApprovalRequest:
    """approval_requests satırı (uygulama tarafı temsili)."""
    user_id         : str | None
    question        : str
    integration_id  : int
    requested_params: dict
    reason          : str
    filters         : dict = field(default_factory=dict)
    session_id      : str | None = None
    status          : str  = ApprovalStatus.PENDING
    external_id     : str  = field(default_factory=lambda: uuid.uuid4().hex)
    request_hash    : str  = ""
    expires_hours   : int  = 48

    def expires_at(self) -> datetime:
        return datetime.now() + timedelta(hours=self.expires_hours)

    def ensure_hash(self) -> str:
        if not self.request_hash:
            self.request_hash = compute_request_hash(
                self.integration_id, self.requested_params, self.question
            )
        return self.request_hash
