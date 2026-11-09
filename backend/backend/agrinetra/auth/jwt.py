from datetime import datetime, timedelta, timezone
from uuid import uuid4
from hashlib import sha256
from jose import jwt, JWTError
from agrinetra.config import settings
def create_access_token(subject: str, role: str, password_hash: str|None=None):
    now=datetime.now(timezone.utc)
    claims={'sub':subject,'role':role,'jti':str(uuid4()),'iat':int(now.timestamp()),'exp':int((now+timedelta(minutes=settings.access_token_minutes)).timestamp())}
    if role=='USER' and password_hash is not None: claims['pwdv']=sha256(password_hash.encode('utf-8')).hexdigest()
    return jwt.encode(claims,settings.jwt_secret,algorithm=settings.jwt_algorithm)
def decode_token(token: str):
    try:
        claims=jwt.decode(token,settings.jwt_secret,algorithms=[settings.jwt_algorithm])
        if not claims.get('sub') or not claims.get('jti') or claims.get('role') not in {'USER','ADMIN'}: return None
        return claims
    except JWTError: return None
