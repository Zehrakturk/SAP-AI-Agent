"""Public/anonim servisler için no-op auth stratejisi."""

from app.services.fetchers.strategies.auth.base import AbstractAuthStrategy


class NoAuthStrategy(AbstractAuthStrategy):
    def apply_to_session(self, session):
        return session

    def build_headers(self) -> dict:
        return {}
