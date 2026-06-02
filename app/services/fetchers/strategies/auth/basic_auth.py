"""HTTP Basic Authentication stratejisi."""

from __future__ import annotations
import base64

from app.services.fetchers.strategies.auth.base import AbstractAuthStrategy


class BasicAuthStrategy(AbstractAuthStrategy):
    """Kullanıcı adı / şifre ile HTTP Basic auth."""

    def __init__(self, username: str, password: str):
        self.username = username or ""
        self.password = password or ""

    def apply_to_session(self, session):
        from requests.auth import HTTPBasicAuth
        session.auth = HTTPBasicAuth(self.username, self.password)
        return session

    def build_headers(self) -> dict:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
