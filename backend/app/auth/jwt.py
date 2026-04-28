"""JSON Web Token encode/decode helpers.

A JWT is a string of the form: `header.payload.signature`, where:
  - header  : metadata (algorithm, type), base64-encoded JSON.
  - payload : claims (subject, expiry), base64-encoded JSON.
  - signature: HMAC of (header + "." + payload) with a secret key.

The signature lets us verify that we issued the token. Without the
secret, an attacker cannot forge or modify the payload.

Why JWT instead of server-side sessions:
  - Stateless: the server doesn't store anything per-user.
  - Easy to scale: any backend instance can verify any token.
  - Containment: each request carries its own auth context.

Trade-off: revocation is harder (we'd need a denylist or short TTL).
We mitigate with short TTL (30 min) — see ACCESS_TOKEN_EXPIRE_MINUTES.

We use HS256 (symmetric HMAC-SHA256). Asymmetric RS256 would be needed
if multiple services signed/verified tokens with separate keys. We have
one server, so symmetric is simpler.
"""

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

from app.config import settings


class TokenInvalid(Exception):
    """Raised when a token is malformed, expired, or has bad signature."""


def create_access_token(user_id: int) -> str:
    """Issue a fresh access token for the given user.

    Claims:
        sub: subject — the user_id. Stored as string per JWT spec convention.
        exp: expiry — Unix timestamp.
        iat: issued at — Unix timestamp.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> int:
    """Verify the signature and expiry, return the user_id.

    Raises TokenInvalid on any failure (bad signature, expired, malformed,
    missing sub).
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise TokenInvalid(str(e)) from e

    sub = payload.get("sub")
    if sub is None:
        raise TokenInvalid("token missing 'sub' claim")

    try:
        return int(sub)
    except (TypeError, ValueError) as e:
        raise TokenInvalid(f"'sub' is not a valid int: {sub!r}") from e
