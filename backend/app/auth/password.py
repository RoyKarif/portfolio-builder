"""Password hashing and verification using bcrypt.

We never store or log plaintext passwords. We never roll our own
hashing — bcrypt is battle-tested.

bcrypt provides three things we need:
  1. **Per-password salt** (random, embedded in the hash). Two users
     with the same password get different hashes.
  2. **Adaptive work factor** (the "rounds" parameter). Brute-force
     attacks are slow; we can increase it as hardware speeds up.
  3. **Memory-hard-ish.** Not as good as argon2, but good enough.

passlib wraps bcrypt with a clean API and handles algorithm versioning
(if we ever migrate to argon2, passlib makes that easy).
"""

from passlib.context import CryptContext


# `deprecated="auto"` tells passlib to flag old-format hashes as needing
# upgrade. With only bcrypt configured, it's a no-op for now — but if
# we ever add a second scheme, passlib will rehash on next login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plaintext password.

    bcrypt has a 72-byte input limit. Most real passwords are well under
    this; we don't enforce a limit at this layer to keep the function
    pure. The schema (Pydantic) caps inputs upstream.
    """
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of plaintext against a stored hash.

    Returns True if the password matches, False otherwise. Constant-time
    means the comparison takes the same wall-time regardless of *where*
    in the hash a mismatch occurs — this prevents timing attacks.
    """
    return pwd_context.verify(plain, hashed)
