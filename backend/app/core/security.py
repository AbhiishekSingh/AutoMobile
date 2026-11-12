from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(sub: str, role: str, token_type: str, expires: timedelta, act: int | None = None) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "exp": datetime.utcnow() + expires,
        "iat": datetime.utcnow(),
    }
    if act:                       # a PBA working under a branch login: the PBA's user id
        payload["act"] = act
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(sub: str, role: str, act: int | None = None) -> str:
    return _create_token(sub, role, "access",
                         timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), act)


def create_refresh_token(sub: str, role: str, act: int | None = None) -> str:
    return _create_token(sub, role, "refresh",
                         timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), act)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
