"""Helpers for deterministic email idempotency keys."""

from hashlib import sha256


def _normalize_recipient(recipient: str) -> str:
    return recipient.strip().lower()


def build_email_idempotency_key(
    event_type: str,
    *,
    recipient: str,
    event_token: str | None = None,
    event_uid: str | None = None,
) -> str:
    """Build a stable idempotency key from normalized event data."""
    normalized_parts = [
        event_type.strip().lower(),
        _normalize_recipient(recipient),
    ]

    if event_token:
        normalized_parts.append(event_token.strip())

    if event_uid:
        normalized_parts.append(event_uid.strip())

    digest = sha256("|".join(normalized_parts).encode("utf-8")).hexdigest()
    return f"email:{event_type.strip().lower()}:{digest}"
