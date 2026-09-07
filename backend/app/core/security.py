import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    *,
    token_type: str = "access",
) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    issued_at = datetime.now(UTC)
    to_encode = {
        "sub": str(subject),
        "iat": issued_at,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "token_type": token_type,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_random_code(length: int = 14) -> str:
    """Generates a random secure 14-character alphanumeric token code."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = str(plain_password).encode("utf-8")
    hash_bytes = str(hashed_password).encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    pwd_bytes = str(password).encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")
