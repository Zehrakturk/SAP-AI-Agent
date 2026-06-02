"""
ApprovalService — onay sürecinin durum makinesi.

create   : gap tespitinden PENDING talep üretir (dedup'lı), audit CREATED.
approve  : PENDING → APPROVED + ingestion_job enqueue, audit APPROVED/JOB_QUEUED.
reject   : PENDING → REJECTED, audit REJECTED.
Geçişler yalnızca buradan yapılır; her geçiş audit_log'a yazılır.
"""

from __future__ import annotations

from app.services.ingestion.models              import (
    ApprovalStatus, AuditAction, GapResult, ApprovalRequest,
)
from app.services.ingestion.approval_repository  import ApprovalRepository
from app.services.ingestion.job_repository       import JobRepository
from app.services.ingestion.audit_repository     import AuditRepository

_ENTITY = "approval_request"


class ApprovalService:

    def __init__(self):
        self.approvals = ApprovalRepository()
        self.jobs      = JobRepository()
        self.audit     = AuditRepository()

    # ─────────────────────────────────────────────────────────────────────
    def create_from_gap(self, gap: GapResult, user_id: str | None,
                         question: str, filters: dict | None,
                         session_id: str | None = None) -> dict:
        """
        Eksik veri tespitinden PENDING onay talebi üretir.
        Aynı talep (request_hash) zaten açıksa onu döndürür (dedup) — yeni satır açmaz.
        Döner: {approval, deduped: bool}
        """
        req = ApprovalRequest(
            user_id          = user_id,
            question         = question,
            integration_id   = gap.integration_id,
            requested_params = gap.params,
            reason           = gap.reason,
            filters          = filters or {},
            session_id       = session_id,
        )
        req.ensure_hash()

        existing = self.approvals.find_open_by_hash(req.request_hash)
        if existing:
            return {"approval": existing, "deduped": True}

        created = self.approvals.create(req)
        self.audit.log(_ENTITY, created["id"], AuditAction.CREATED,
                       actor=user_id or "anon",
                       detail={"integration_id": gap.integration_id,
                               "params": gap.params, "reason": gap.reason})
        return {"approval": created, "deduped": False}

    # ─────────────────────────────────────────────────────────────────────
    def approve(self, approval_id: int, admin_id: str,
                note: str | None = None) -> dict:
        """PENDING → APPROVED + job enqueue. Idempotent: zaten APPROVED ise mevcut job'u döndürür."""
        appr = self.approvals.get_by_id(approval_id)
        if not appr:
            return {"error": "Onay talebi bulunamadı.", "code": 404}
        if appr["status"] == ApprovalStatus.APPROVED:
            job = self.jobs.get_by_approval(approval_id)
            return {"approval": appr, "job_id": job["id"] if job else None, "already": True}
        if appr["status"] != ApprovalStatus.PENDING:
            return {"error": f"Bu talep '{appr['status']}' durumunda, onaylanamaz.", "code": 409}

        self.approvals.update_status(approval_id, ApprovalStatus.APPROVED,
                                     decided_by=admin_id, decision_note=note)
        self.audit.log(_ENTITY, approval_id, AuditAction.APPROVED,
                       actor=admin_id, detail={"note": note})

        job_id = self.jobs.enqueue(
            approval_request_id = approval_id,
            integration_id      = appr["integration_id"],
            params              = appr.get("requested_params") or {},
        )
        self.audit.log(_ENTITY, approval_id, AuditAction.JOB_QUEUED,
                       actor=admin_id, detail={"job_id": job_id})
        return {"approval": self.approvals.get_by_id(approval_id),
                "job_id": job_id, "already": False}

    # ─────────────────────────────────────────────────────────────────────
    def reject(self, approval_id: int, admin_id: str,
               note: str | None = None) -> dict:
        appr = self.approvals.get_by_id(approval_id)
        if not appr:
            return {"error": "Onay talebi bulunamadı.", "code": 404}
        if appr["status"] != ApprovalStatus.PENDING:
            return {"error": f"Bu talep '{appr['status']}' durumunda, reddedilemez.", "code": 409}

        self.approvals.update_status(approval_id, ApprovalStatus.REJECTED,
                                     decided_by=admin_id, decision_note=note)
        self.audit.log(_ENTITY, approval_id, AuditAction.REJECTED,
                       actor=admin_id, detail={"note": note})
        return {"approval": self.approvals.get_by_id(approval_id)}

    # ─────────────────────────────────────────────────────────────────────
    def _status_dict(self, appr: dict, requester_id: str | None) -> dict:
        """approval + job + (sahibine) sonuç birleşik durum sözlüğü."""
        owner    = str(appr.get("user_id") or "")
        is_owner = requester_id is not None and str(requester_id) == owner
        job      = self.jobs.get_by_approval(appr["id"])
        out = {
            "approval_id"     : appr["id"],
            "external_id"     : appr.get("external_id"),
            "status"          : appr["status"],
            "reason"          : appr.get("reason"),
            "integration_id"  : appr.get("integration_id"),
            "requested_params": appr.get("requested_params"),
            "job"             : {
                "status"        : job["status"] if job else None,
                "rows_written"  : job.get("rows_written") if job else None,
                "chunks_indexed": job.get("chunks_indexed") if job else None,
                "error_message" : job.get("error_message") if job else None,
            } if job else None,
        }
        if is_owner:
            out["result"] = appr.get("result")
        return out

    def status_for_external(self, external_id: str,
                            requester_id: str | None) -> dict | None:
        """Kullanıcı polling'i için tek talebin birleşik durumu (PII sahip korumalı)."""
        appr = self.approvals.get_by_external(external_id)
        if not appr:
            return None
        return self._status_dict(appr, requester_id)

    def list_for_session(self, session_id: str,
                         requester_id: str | None) -> list[dict]:
        """Bir sohbetteki tüm onay taleplerinin birleşik durumları (kart yeniden çizimi)."""
        rows = self.approvals.list_by_session(session_id, user_id=requester_id)
        return [self._status_dict(a, requester_id) for a in rows]
