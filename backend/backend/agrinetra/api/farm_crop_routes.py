from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from agrinetra.database.connection import get_db
from agrinetra.database.models import User,Farm,Crop
from agrinetra.auth.dependencies import get_current_user
from agrinetra.api.schemas import FarmIn,FarmOut,CropIn,CropOut
router=APIRouter(prefix='/api',tags=['farms and crops'])
def owned_farm(db,user_id,farm_id):
    item=db.query(Farm).filter(Farm.id==farm_id,Farm.user_id==user_id).first()
    if not item: raise HTTPException(404,'Farm not found.')
    return item
def owned_crop(db,user_id,crop_id):
    item=db.query(Crop).filter(Crop.id==crop_id,Crop.user_id==user_id).first()
    if not item: raise HTTPException(404,'Crop not found.')
    return item
@router.get('/farms',response_model=list[FarmOut])
def list_farms(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return db.query(Farm).filter(Farm.user_id==user.id).order_by(Farm.created_at.desc()).all()
@router.post('/farms',response_model=FarmOut,status_code=201)
def create_farm(payload:FarmIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    item=Farm(user_id=user.id,**payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@router.get('/farms/{farm_id}',response_model=FarmOut)
def get_farm(farm_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)): return owned_farm(db,user.id,farm_id)
@router.put('/farms/{farm_id}',response_model=FarmOut)
def update_farm(farm_id:str,payload:FarmIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    item=owned_farm(db,user.id,farm_id)
    for k,v in payload.model_dump().items(): setattr(item,k,v)
    db.commit(); db.refresh(item); return item
@router.delete('/farms/{farm_id}')
def delete_farm(farm_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.delete(owned_farm(db,user.id,farm_id)); db.commit(); return {'status':'success'}
@router.get('/crops',response_model=list[CropOut])
def list_crops(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return db.query(Crop).filter(Crop.user_id==user.id).order_by(Crop.created_at.desc()).all()
@router.post('/crops',response_model=CropOut,status_code=201)
def create_crop(payload:CropIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    owned_farm(db,user.id,payload.farm_id)
    item=Crop(user_id=user.id,**payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@router.get('/crops/{crop_id}',response_model=CropOut)
def get_crop(crop_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)): return owned_crop(db,user.id,crop_id)
@router.put('/crops/{crop_id}',response_model=CropOut)
def update_crop(crop_id:str,payload:CropIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    item=owned_crop(db,user.id,crop_id); owned_farm(db,user.id,payload.farm_id)
    for k,v in payload.model_dump().items(): setattr(item,k,v)
    db.commit(); db.refresh(item); return item
@router.delete('/crops/{crop_id}')
def delete_crop(crop_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.delete(owned_crop(db,user.id,crop_id)); db.commit(); return {'status':'success'}
