"""Reproducible customer capability, isolated from authentication/quote tokens."""

import hashlib
import hmac

from app.core.config import settings


def acceptance_token(invoice_id: str, delivery_id: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"invoice-acceptance:{invoice_id}:{delivery_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
