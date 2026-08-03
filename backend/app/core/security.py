import bcrypt
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from app.config import settings

ALGORITHM = "HS256"

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_random_code(length: int = 14) -> str:
    """Generates a random secure 14-character alphanumeric token code."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = str(plain_password).encode('utf-8')[:72]
        hash_bytes = str(hashed_password).encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = str(password).encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
