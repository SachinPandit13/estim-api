import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt

SECRET_KEY = "estim_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480


def _get_bytes(val: str | bytes) -> bytes:
    if isinstance(val, bytes):
        return val
    return str(val).encode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password without length limitation errors."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = _get_bytes(plain_password)[:72]
        hash_bytes = _get_bytes(hashed_password)
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash password using native bcrypt, safely slicing to 72 bytes so no error is ever thrown."""
    pwd_bytes = _get_bytes(password)[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


