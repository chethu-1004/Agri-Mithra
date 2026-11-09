from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from agrinetra.database.connection import get_db
from agrinetra.database.models import User, RevokedToken
from agrinetra.api.schemas import UserRegister, FarmerLoginRequest, PasswordChange, TokenResponse, UserOut, UserUpdate
from agrinetra.auth.password import hash_password, verify_password
from agrinetra.auth.jwt import create_access_token, decode_token
from agrinetra.auth.dependencies import get_current_user, bearer
from agrinetra.config import settings
from agrinetra.storage.service import save_image
router=APIRouter(prefix='/api',tags=['authentication'])
def normalize_phone(value:str|None)->str:
    digits=''.join(character for character in (value or '') if character.isdigit())
    return digits[-10:] if len(digits)>=10 else ''
@router.post('/auth/register',response_model=UserOut,status_code=201)
def register(payload:UserRegister,db:Session=Depends(get_db)):
    email=str(payload.email).lower()
    if db.query(User).filter(User.email==email).first(): raise HTTPException(409,'An account with this email already exists.')
    phone=payload.phone.strip() if payload.phone else None
    normalized_phone=normalize_phone(phone)
    if normalized_phone and any(normalize_phone(existing) == normalized_phone for (existing,) in db.query(User.phone).filter(User.phone.isnot(None)).all()):
        raise HTTPException(409,'An account with this mobile number already exists.')
    try: user=User(name=payload.name.strip(),email=email,phone=phone,password_hash=hash_password(payload.password)); db.add(user); db.commit(); db.refresh(user); return user
    except ValueError as exc: raise HTTPException(422,str(exc))
    except IntegrityError: db.rollback(); raise HTTPException(409,'An account with this email already exists.')
@router.post('/auth/login',response_model=TokenResponse)
def login(payload:FarmerLoginRequest,request:Request,db:Session=Depends(get_db)):
    identifier=(payload.identifier or payload.email or payload.phone or '').strip()
    if not identifier: raise HTTPException(422,'Enter your email address or mobile number.')
    if '@' in identifier:
        user=db.query(User).filter(User.email==identifier.lower()).first()
    else:
        normalized_phone=normalize_phone(identifier)
        matches=[candidate for candidate in db.query(User).filter(User.phone.isnot(None)).all() if normalize_phone(candidate.phone)==normalized_phone] if normalized_phone else []
        user=matches[0] if len(matches)==1 else None
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,'Invalid email/mobile number or password.')
    if user.status!='ACTIVE': raise HTTPException(403,'Account is inactive.')
    user.last_login=datetime.now(timezone.utc); db.commit()
    return TokenResponse(access_token=create_access_token(user.id,'USER',user.password_hash),role='USER')
@router.post('/auth/change-password')
def change_password(payload:PasswordChange,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if not verify_password(payload.current_password,user.password_hash):
        raise HTTPException(400,'Current password is incorrect.')
    try: user.password_hash=hash_password(payload.new_password)
    except ValueError as exc: raise HTTPException(422,str(exc))
    db.commit()
    return {'status':'success','message':'Password changed. Other sessions have been signed out.','access_token':create_access_token(user.id,'USER',user.password_hash)}
@router.post('/auth/logout')
def logout(credentials=Depends(bearer),db:Session=Depends(get_db)):
    if credentials:
        claims=decode_token(credentials.credentials)
        if claims and not db.get(RevokedToken,claims['jti']):
            exp=datetime.fromtimestamp(claims['exp'],timezone.utc); db.add(RevokedToken(jti=claims['jti'],expires_at=exp)); db.commit()
    return {'status':'success','message':'Logged out.'}
@router.get('/users/me',response_model=UserOut)
def me(user:User=Depends(get_current_user)): return user

@router.post('/users/me/profile-image')
async def upload_profile_image(file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _,storage_key=await save_image(file)
    user.profile_image=storage_key
    db.commit(); db.refresh(user)
    return {'profile_image':user.profile_image}

@router.get('/users/me/profile-image')
def get_profile_image(user:User=Depends(get_current_user)):
    key=user.profile_image
    if not key or Path(key).name!=key: raise HTTPException(404,'Profile image not found.')
    path=Path(settings.upload_dir)/key
    if not path.is_file(): raise HTTPException(404,'Profile image is no longer available.')
    return FileResponse(path)

@router.put('/users/me',response_model=UserOut)
def update_me(payload:UserUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(user,k,v)
    db.commit(); db.refresh(user); return user
