from __future__ import annotations


def normalize_portal_base_url(base_url: str) -> str | None:
    if not isinstance(base_url, str):
        return None

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return None

    if not normalized.startswith(("http://", "https://")):
        return None

    return normalized


def build_portal_url(base_url: str, path: str) -> str | None:
    normalized_base = normalize_portal_base_url(base_url)
    if not normalized_base:
        return None

    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{normalized_base}{normalized_path}"
