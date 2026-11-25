import inspect
from typing import Any


async def resolve_current_user(handler: Any) -> Any:
    identity_provider = getattr(handler, "identity_provider", None)
    if identity_provider is not None:
        user = identity_provider.get_user(handler)
        if inspect.isawaitable(user) or hasattr(user, "__await__"):
            user = await user
        return user
    return getattr(handler, "current_user", None)


def extract_user_scope(user: Any, fallback: str = "local") -> str:
    if user is None:
        return fallback

    if isinstance(user, dict):
        raw = (
            user.get("username")
            or user.get("name")
            or user.get("id")
            or user.get("user_id")
        )
    else:
        raw = (
            getattr(user, "username", None)
            or getattr(user, "name", None)
            or getattr(user, "id", None)
            or getattr(user, "user_id", None)
        )

    return str(raw) if raw else fallback