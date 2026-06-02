"""Bearer Token (JWT vb.) auth stratejisi."""

from __future__ import annotations
from app.services.fetchers.strategies.auth.base import AbstractAuthStrategy


class BearerTokenStrategy(AbstractAuthStrategy):
    """Authorization: Bearer <token> header'ı ekler."""

    def __init__(self, token: str):
        self.token = (token or "").strip()

    def apply_to_session(self, session):
        if self.token:
            session.headers.update({"Authorization": f"Bearer {self.token}"})
        return session

    def build_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}
