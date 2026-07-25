"""API route inventory facade; FastAPI registration remains in api.main."""


def route_names() -> tuple[str, ...]:
    return ("/holon/{name}/chat", "/holon/{name}/chat/history")


__all__ = ["route_names"]
