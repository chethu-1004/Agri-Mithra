from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
_hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
def hash_password(password: str) -> str:
    if len(password)<10: raise ValueError('Password must contain at least 10 characters.')
    return _hasher.hash(password)
def verify_password(password: str, encoded: str) -> bool:
    try: return _hasher.verify(encoded,password)
    except (VerifyMismatchError,VerificationError,ValueError): return False
