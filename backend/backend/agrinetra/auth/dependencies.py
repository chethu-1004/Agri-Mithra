from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from hashlib import sha256
from hmac import compare_digest
from agrinetra.database.connection import get_db
from agrinetra.database.models import User, AdminUser, RevokedToken
from agrinetra.auth.jwt import decode_token
bearer=HTTPBearer(auto_error=False)
def _claims(credentials,db):
    if not credentials: raise HTTPException(status_code=401,detail='Authentication required',headers={'WWW-Authenticate':'Bearer'})
    claims=decode_token(credentials.credentials)
    if not claims or db.get(RevokedToken,claims['jti']): raise HTTPException(status_code=401,detail='Invalid or expired token')
    return claims
def get_current_user(credentials: HTTPAuthorizationCredentials|None=Depends(bearer),db: Session=Depends(get_db)):
    claims=_claims(credentials,db)
    if claims['role']!='USER': raise HTTPException(status_code=403,detail='Farmer account required')
    user=db.get(User,claims['sub'])
    if not user or user.status!='ACTIVE': raise HTTPException(status_code=403,detail='Account is inactive')
    expected_password_version=sha256(user.password_hash.encode('utf-8')).hexdigest()
    if not claims.get('pwdv') or not compare_digest(claims['pwdv'],expected_password_version): raise HTTPException(status_code=401,detail='Your password changed. Please sign in again.')
    return user
def get_current_admin(credentials: HTTPAuthorizationCredentials|None=Depends(bearer),db: Session=Depends(get_db)):
    claims=_claims(credentials,db)
    if claims['role']!='ADMIN': raise HTTPException(status_code=403,detail='Admin role required')
    admin=db.get(AdminUser,claims['sub'])
    if not admin or admin.status!='ACTIVE': raise HTTPException(status_code=403,detail='Admin account is inactive')
    return admin
