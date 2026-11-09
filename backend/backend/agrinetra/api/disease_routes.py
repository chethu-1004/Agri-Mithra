from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from agrinetra.database.connection import get_db
from agrinetra.database.models import User,Farm,Crop,DiseaseScan,Notification
from agrinetra.auth.dependencies import get_current_user
from agrinetra.storage.service import save_image
from agrinetra.database.models import new_id
from agrinetra.disease_detection.model_loader import predictor,ModelUnavailable
from agrinetra.disease_detection.recommendations import get_recommendation
from agrinetra.services.plant_analysis import build_disease_analysis
from agrinetra.config import settings
router=APIRouter(prefix='/api/disease',tags=['disease detection'])
@router.post('/predict')
async def predict(file:UploadFile=File(...),farm_id:str|None=Form(default=None),crop_id:str|None=Form(default=None),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if farm_id and not db.query(Farm).filter(Farm.id==farm_id,Farm.user_id==user.id).first(): raise HTTPException(404,'Farm not found.')
    if crop_id:
        crop=db.query(Crop).filter(Crop.id==crop_id,Crop.user_id==user.id).first()
        if not crop: raise HTTPException(404,'Crop not found.')
        if farm_id and crop.farm_id!=farm_id: raise HTTPException(422,'Crop does not belong to this farm.')
        farm_id=crop.farm_id
    image_path,storage_key=await save_image(file)
    try: label,confidence=predictor.predict(image_path)
    except ModelUnavailable as exc:
        Path(image_path).unlink(missing_ok=True)
        raise HTTPException(503,str(exc))
    disease=label.replace('_',' ').strip()
    status='SUCCESS' if confidence>=settings.prediction_threshold else 'UNCERTAIN'
    scan_id=new_id()
    scan=DiseaseScan(id=scan_id,user_id=user.id,farm_id=farm_id,crop_id=crop_id,image_url=f'/api/disease/history/{scan_id}/image',image_storage_key=storage_key,predicted_disease=disease,predicted_class=label,confidence=confidence,model_version=str(predictor.metadata.get('version',settings.model_version)),status=status)
    db.add(scan)
    db.add(Notification(user_id=user.id,title='Disease scan completed',message=('A possible result was detected: '+disease) if status=='SUCCESS' else 'The scan result was uncertain. Try another clear image.'))
    db.commit(); db.refresh(scan)
    if status=='UNCERTAIN':
        return {'status':'uncertain','message':'The image could not be classified with sufficient confidence. Try another clear image or consult a local agricultural expert.','confidence':confidence,'scan_id':scan.id,'analysis':build_disease_analysis(label,confidence,status=status)}
    return {'status':'success','prediction':{'disease':disease,'predicted_class':label,'confidence':confidence},'recommendation':get_recommendation(db,label),'scan_id':scan.id,'analysis':build_disease_analysis(label,confidence,status=status)}
@router.get('/history')
def history(db:Session=Depends(get_db),user:User=Depends(get_current_user),limit:int=50,offset:int=0):
    limit=max(1,min(limit,100)); rows=db.query(DiseaseScan).filter(DiseaseScan.user_id==user.id).order_by(DiseaseScan.created_at.desc()).offset(offset).limit(limit).all()
    return [{'id':x.id,'farm_id':x.farm_id,'crop_id':x.crop_id,'image_url':x.image_url,'predicted_disease':x.predicted_disease,'predicted_class':x.predicted_class,'confidence':x.confidence,'model_version':x.model_version,'status':x.status,'created_at':x.created_at} for x in rows]
@router.get('/history/{scan_id}/image')
def get_scan_image(scan_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scan=db.query(DiseaseScan).filter(DiseaseScan.id==scan_id,DiseaseScan.user_id==user.id).first()
    if not scan or not scan.image_storage_key: raise HTTPException(404,'Scan image not found.')
    if Path(scan.image_storage_key).name!=scan.image_storage_key: raise HTTPException(404,'Scan image not found.')
    path=Path(settings.upload_dir)/scan.image_storage_key
    if not path.is_file(): raise HTTPException(404,'Scan image is no longer available.')
    return FileResponse(path)
@router.get('/history/{scan_id}')
def get_history(scan_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    x=db.query(DiseaseScan).filter(DiseaseScan.id==scan_id,DiseaseScan.user_id==user.id).first()
    if not x: raise HTTPException(404,'Scan not found.')
    return {'id':x.id,'farm_id':x.farm_id,'crop_id':x.crop_id,'image_url':x.image_url,'predicted_disease':x.predicted_disease,'predicted_class':x.predicted_class,'confidence':x.confidence,'model_version':x.model_version,'status':x.status,'created_at':x.created_at}



