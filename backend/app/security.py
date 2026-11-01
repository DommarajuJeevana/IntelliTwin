"""
Password hashing (bcrypt, same algorithm bcryptjs used - hashes are
cross-compatible with any existing data) and JWT signing/verification
(python-jose, same HS256 default jsonwebtoken used).

Mirrors: backend/models/User.js (hashPassword/comparePassword) and
backend/utils/token.js (signToken/verifyToken).

NOTE: this talks to the `bcrypt` library directly instead of going through
passlib. passlib is unmaintained and its bcrypt handler breaks on bcrypt
>=4.1 (it probes `bcrypt.__about__.__version__`, which newer bcrypt no
longer ships) - and bcrypt 5.0+ is what actually added Python 3.14 wheels,
so passlib has to go rather than get pinned to an old, unsupported bcrypt.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"

# bcrypt has always silently used only the first 72 bytes of the password;
# bcryptjs (the old Node backend) does the same. bcrypt>=5 raises a
# ValueError instead of silently truncating, so we truncate ourselves to
# keep both the old behavior and cross-compatibility with existing hashes.
_MAX_PASSWORD_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_PASSWORD_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(candidate: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(candidate), password_hash.encode("utf-8"))
    except Exception:
        return False


def sign_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRES_IN_DAYS)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
