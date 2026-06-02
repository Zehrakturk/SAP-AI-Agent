"""Authentication strategies — Basic, Bearer, OAuth2, None."""

from app.services.fetchers.strategies.auth.base         import AbstractAuthStrategy
from app.services.fetchers.strategies.auth.basic_auth   import BasicAuthStrategy
from app.services.fetchers.strategies.auth.bearer_token import BearerTokenStrategy
from app.services.fetchers.strategies.auth.none_auth    import NoAuthStrategy

__all__ = [
    "AbstractAuthStrategy",
    "BasicAuthStrategy",
    "BearerTokenStrategy",
    "NoAuthStrategy",
    "create_auth_strategy",
]


def create_auth_strategy(auth_type: str, username: str | None = None,
                         password: str | None = None,
                         extra_config: dict | None = None) -> AbstractAuthStrategy:
    """Mini factory — auth_type'a göre uygun strateji üretir."""
    auth_type = (auth_type or "BASIC").upper()
    extra = extra_config or {}

    if auth_type == "BASIC":
        return BasicAuthStrategy(username or "", password or "")
    if auth_type == "BEARER":
        # Token: önce extra_config.token, yoksa password alanında saklanmış olabilir
        token = extra.get("token") or password or ""
        return BearerTokenStrategy(token)
    if auth_type in ("NONE", "ANON", "ANONYMOUS"):
        return NoAuthStrategy()

    raise ValueError(f"Bilinmeyen auth_type: {auth_type}")
