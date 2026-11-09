import json
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import func,case
from fastapi import APIRouter,Depends,HTTPException,Request,Query,Form,File,UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from agrinetra.database.connection import get_db
from agrinetra.database.models import AdminUser,User,Farm,Crop,DiseaseScan,AuditLog,ModelVersion,ChatMessage,Notification,MarketProduct,MarketContact,MarketListing,MarketOrder
from agrinetra.api.schemas import LoginRequest,TokenResponse,StatusUpdate,AdminPasswordReset,MarketProductIn,MarketProductStatus,MarketContactIn,MarketContactStatus
from agrinetra.auth.password import verify_password,hash_password
from agrinetra.auth.jwt import create_access_token
from agrinetra.auth.dependencies import get_current_admin
from agrinetra.config import settings
from agrinetra.disease_detection.model_loader import predictor
from agrinetra.services.weather import fetch_weather,find_weather_location
from agrinetra.storage.service import save_image
router=APIRouter(prefix='/api/admin',tags=['admin'])
def audit(db,admin,action,target_type=None,target_id=None,request=None,details=None):
    db.add(AuditLog(admin_id=admin.id,action=action,target_type=target_type,target_id=target_id,ip_address=request.client.host if request and request.client else None,details=details))

def _product_json(product):
    return {'id':product.id,'name':product.name,'category':product.category,'brand':product.brand,'description':product.description,'price':product.price,'emoji':product.emoji,'image_url':f'/api/market/products/{product.id}/image' if product.image_storage_key else None,'is_active':product.is_active,'created_at':product.created_at,'updated_at':product.updated_at}

def _contact_json(contact):
    return {'id':contact.id,'kind':contact.kind,'name':contact.name,'organization':contact.organization,'interests':contact.interests,'phone':contact.phone,'email':contact.email,'location':contact.location,'description':contact.description,'is_active':contact.is_active,'created_at':contact.created_at,'updated_at':contact.updated_at}

@router.get('/market-products')
def market_products(db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    del admin
    return [_product_json(row) for row in db.query(MarketProduct).order_by(MarketProduct.created_at.desc()).all()]

@router.post('/market-products')
def create_market_product(payload:MarketProductIn,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    product=MarketProduct(**payload.model_dump(),created_by_admin_id=admin.id)
    db.add(product); db.flush(); audit(db,admin,'MARKET_PRODUCT_CREATED','MARKET_PRODUCT',product.id,request,{'name':product.name}); db.commit(); db.refresh(product)
    return _product_json(product)

@router.post('/market-products/with-image')
async def create_market_product_with_image(
    request:Request,
    name:str=Form(min_length=1,max_length=160),
    category:str=Form(min_length=1,max_length=80),
    price:float=Form(gt=0,le=100000000),
    brand:str|None=Form(default=None,max_length=160),
    description:str|None=Form(default=None,max_length=2000),
    emoji:str=Form(default='🌱',max_length=16),
    is_active:bool=Form(default=True),
    file:UploadFile=File(...),
    db:Session=Depends(get_db),
    admin:AdminUser=Depends(get_current_admin),
):
    try:
        payload=MarketProductIn(name=name,category=category,brand=brand or None,description=description or None,price=price,emoji=emoji or '🌱',is_active=is_active)
    except ValidationError as exc:
        errors=[{'loc':list(item.get('loc',())),'msg':item.get('msg','Invalid product details.'),'type':item.get('type','value_error')} for item in exc.errors()]
        raise HTTPException(422,errors)
    stored_path,storage_key=await save_image(file)
    product=MarketProduct(**payload.model_dump(),image_storage_key=storage_key,created_by_admin_id=admin.id)
    try:
        db.add(product); db.flush(); audit(db,admin,'MARKET_PRODUCT_CREATED','MARKET_PRODUCT',product.id,request,{'name':product.name,'image_added':True}); db.commit(); db.refresh(product)
    except Exception:
        db.rollback()
        Path(stored_path).unlink(missing_ok=True)
        raise
    return _product_json(product)

@router.patch('/market-products/{product_id}/status')
def set_market_product_status(product_id:str,payload:MarketProductStatus,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    product=db.get(MarketProduct,product_id)
    if not product: raise HTTPException(404,'Marketplace product not found.')
    product.is_active=payload.is_active; audit(db,admin,'MARKET_PRODUCT_STATUS_CHANGED','MARKET_PRODUCT',product.id,request,{'is_active':product.is_active}); db.commit()
    return _product_json(product)

@router.get('/market-contacts')
def market_contacts(db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    del admin
    return [_contact_json(row) for row in db.query(MarketContact).order_by(MarketContact.created_at.desc()).all()]

@router.post('/market-contacts',status_code=201)
def create_market_contact(payload:MarketContactIn,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    if not payload.phone and not payload.email:
        raise HTTPException(422,'Add a phone number or email so farmers can contact this supplier or buyer.')
    contact=MarketContact(**payload.model_dump(),created_by_admin_id=admin.id)
    db.add(contact); db.flush(); audit(db,admin,'MARKET_CONTACT_CREATED','MARKET_CONTACT',contact.id,request,{'kind':contact.kind,'name':contact.name}); db.commit(); db.refresh(contact)
    return _contact_json(contact)

@router.patch('/market-contacts/{contact_id}/status')
def set_market_contact_status(contact_id:str,payload:MarketContactStatus,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    contact=db.get(MarketContact,contact_id)
    if not contact: raise HTTPException(404,'Supplier or buyer record not found.')
    contact.is_active=payload.is_active; audit(db,admin,'MARKET_CONTACT_STATUS_CHANGED','MARKET_CONTACT',contact.id,request,{'is_active':contact.is_active}); db.commit(); db.refresh(contact)
    return _contact_json(contact)

@router.get('/market-listings')
def market_listings(limit:int=200,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    del admin
    rows=(db.query(MarketListing,User).join(User,User.id==MarketListing.user_id).order_by(MarketListing.created_at.desc()).limit(max(1,min(limit,500))).all())
    return [{'id':listing.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'crop_name':listing.crop_name,'variety':listing.variety,'quantity':listing.quantity,'price':listing.price,'harvest':listing.harvest,'location':listing.location,'grade':listing.grade,'status':listing.status,'created_at':listing.created_at} for listing,user in rows]

@router.get('/market-orders')
def market_orders(limit:int=200,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    del admin
    rows=(db.query(MarketOrder,MarketProduct,User).join(MarketProduct,MarketProduct.id==MarketOrder.product_id).join(User,User.id==MarketOrder.user_id).order_by(MarketOrder.created_at.desc()).limit(max(1,min(limit,500))).all())
    return [{'id':order.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'product_id':product.id,'product_name':product.name,'quantity':order.quantity,'unit_price':order.unit_price,'total':round(order.unit_price*order.quantity,2),'status':order.status,'created_at':order.created_at} for order,product,user in rows]

@router.get('/weather/location')
async def admin_weather_location(name:str=Query(min_length=2,max_length=120),admin:AdminUser=Depends(get_current_admin)):
    del admin
    return await find_weather_location(name)

@router.get('/weather')
async def admin_weather(latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180),history_days:int=Query(default=7,ge=1,le=14),forecast_days:int=Query(default=8,ge=1,le=16),admin:AdminUser=Depends(get_current_admin)):
    del admin
    if settings.weather_provider!='open-meteo': raise HTTPException(503,'Configured weather provider is not implemented.')
    return await fetch_weather(latitude,longitude,history_days,forecast_days)
@router.post('/auth/login',response_model=TokenResponse)
def admin_login(payload:LoginRequest,request:Request,db:Session=Depends(get_db)):
    admin=db.query(AdminUser).filter(AdminUser.email==str(payload.email).lower()).first()
    if not admin or not verify_password(payload.password,admin.password_hash): raise HTTPException(401,'Invalid admin email or password.')
    if admin.status!='ACTIVE' or admin.role!='ADMIN': raise HTTPException(403,'Admin account is inactive.')
    admin.last_login=datetime.now(timezone.utc); db.commit(); audit(db,admin,'ADMIN_LOGIN',request=request); db.commit()
    return TokenResponse(access_token=create_access_token(admin.id,'ADMIN'),role='ADMIN')

@router.get('/me')
def admin_profile(admin:AdminUser=Depends(get_current_admin)):
    return {'id':admin.id,'name':admin.name,'email':admin.email,'role':admin.role,'status':admin.status,'created_at':admin.created_at,'last_login':admin.last_login}

@router.get('/dashboard')
def dashboard(request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    latest=db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).first()
    meta_path=Path(settings.model_metadata_path)
    if not meta_path.is_absolute(): meta_path=Path(__file__).resolve().parents[2]/meta_path
    try: model_info=json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception: model_info={}
    result={'total_users':db.query(func.count(User.id)).scalar() or 0,'active_users':db.query(func.count(User.id)).filter(User.status=='ACTIVE').scalar() or 0,'total_farms':db.query(func.count(Farm.id)).scalar() or 0,'total_crops':db.query(func.count(Crop.id)).scalar() or 0,'total_scans':db.query(func.count(DiseaseScan.id)).scalar() or 0,'total_ai_queries':db.query(func.count(ChatMessage.id)).filter(ChatMessage.role=='USER').scalar() or 0,'total_notifications':db.query(func.count(Notification.id)).scalar() or 0,'model_version':latest.version if latest else model_info.get('version',settings.model_version),'supported_classes':latest.num_classes if latest else model_info.get('num_classes',0),'model_status':'READY' if predictor.model is not None else 'MODEL_NOT_INSTALLED','recent_users':[],'recent_activity':[]}
    result['system_status']={'api':'UP','database':'UP','model':'READY' if predictor.model is not None else 'MODEL_NOT_INSTALLED','storage':'READY' if settings.storage_provider=='local' else 'ADAPTER_REQUIRED'}
    result['recent_users']=[{'id':u.id,'name':u.name,'email':u.email,'status':u.status,'created_at':u.created_at} for u in db.query(User).order_by(User.created_at.desc()).limit(5).all()]
    result['recent_activity']=[{'action':x.action,'target_type':x.target_type,'target_id':x.target_id,'timestamp':x.timestamp} for x in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()]
    return result
@router.get('/users')
def users(q:str|None=None,status_filter:str|None=Query(default=None,alias='status'),limit:int=50,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    query=db.query(User)
    if q: query=query.filter((User.name.ilike(f'%{q}%'))|(User.email.ilike(f'%{q}%')))
    if status_filter in {'ACTIVE','DISABLED'}: query=query.filter(User.status==status_filter)
    rows=query.order_by(User.created_at.desc()).offset(max(offset,0)).limit(max(1,min(limit,100))).all()
    return [{'id':u.id,'name':u.name,'email':u.email,'phone':u.phone,'status':u.status,'created_at':u.created_at,'last_login':u.last_login} for u in rows]
@router.get('/users/{user_id}')
def user_detail(user_id:str,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,'User not found.')
    audit(db,admin,'USER_VIEWED','USER',user_id,request); db.commit()
    return {'id':u.id,'name':u.name,'email':u.email,'phone':u.phone,'status':u.status,'created_at':u.created_at,'last_login':u.last_login,'farms':[{'id':x.id,'farm_name':x.farm_name,'location':x.location} for x in db.query(Farm).filter(Farm.user_id==u.id).all()],'crops':[{'id':x.id,'farm_id':x.farm_id,'crop_name':x.crop_name,'variety':x.variety} for x in db.query(Crop).filter(Crop.user_id==u.id).all()],'disease_scans':[{'id':x.id,'predicted_disease':x.predicted_disease,'confidence':x.confidence,'status':x.status,'created_at':x.created_at} for x in db.query(DiseaseScan).filter(DiseaseScan.user_id==u.id).order_by(DiseaseScan.created_at.desc()).limit(100).all()]}
@router.post('/users/{user_id}/password-reset')
def reset_user_password(user_id:str,payload:AdminPasswordReset,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    user=db.get(User,user_id)
    if not user: raise HTTPException(404,'User not found.')
    try: user.password_hash=hash_password(payload.new_password)
    except ValueError as exc: raise HTTPException(422,str(exc))
    audit(db,admin,'USER_PASSWORD_RESET','USER',user_id,request,{'sessions_revoked':True})
    db.commit()
    return {'status':'success','message':'Password reset. Existing user sessions have been signed out.'}
@router.put('/users/{user_id}/status')
def set_user_status(user_id:str,payload:StatusUpdate,request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,'User not found.')
    u.status=payload.status; audit(db,admin,'USER_STATUS_CHANGED','USER',user_id,request,{'status':payload.status}); db.commit()
    return {'id':u.id,'status':u.status}
@router.get('/farms')
def all_farms(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=(db.query(Farm,User).join(User,User.id==Farm.user_id).order_by(Farm.created_at.desc()).offset(max(0,offset)).limit(max(1,min(limit,200))).all())
    return [{'id':farm.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'farm_name':farm.farm_name,'location':farm.location,'area':farm.area,'created_at':farm.created_at} for farm,user in rows]
@router.get('/crops')
def all_crops(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=(db.query(Crop,User,Farm).join(User,User.id==Crop.user_id).join(Farm,Farm.id==Crop.farm_id).order_by(Crop.created_at.desc()).offset(max(0,offset)).limit(max(1,min(limit,200))).all())
    return [{'id':crop.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'farm_id':farm.id,'farm_name':farm.farm_name,'location':farm.location,'crop_name':crop.crop_name,'variety':crop.variety,'sowing_date':crop.sowing_date,'expected_harvest_date':crop.expected_harvest_date,'created_at':crop.created_at} for crop,user,farm in rows]
@router.get('/disease-scans')
def all_scans(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=(db.query(DiseaseScan,User,Crop,Farm).join(User,User.id==DiseaseScan.user_id).outerjoin(Crop,Crop.id==DiseaseScan.crop_id).outerjoin(Farm,Farm.id==DiseaseScan.farm_id).order_by(DiseaseScan.created_at.desc()).offset(max(0,offset)).limit(max(1,min(limit,200))).all())
    return [{'id':scan.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'farm_id':scan.farm_id,'farm_name':farm.farm_name if farm else None,'crop_id':scan.crop_id,'crop_name':crop.crop_name if crop else None,'predicted_disease':scan.predicted_disease,'predicted_class':scan.predicted_class,'confidence':scan.confidence,'model_version':scan.model_version,'status':scan.status,'created_at':scan.created_at} for scan,user,crop,farm in rows]
@router.get('/ai-queries')
def all_ai_queries(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=(db.query(ChatMessage,User).join(User,User.id==ChatMessage.user_id).filter(ChatMessage.role=='USER').order_by(ChatMessage.created_at.desc()).offset(max(0,offset)).limit(max(1,min(limit,200))).all())
    return [{'id':message.id,'session_id':message.session_id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'query':message.content,'created_at':message.created_at} for message,user in rows]
@router.get('/notifications')
def all_notifications(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=(db.query(Notification,User).join(User,User.id==Notification.user_id).order_by(Notification.created_at.desc()).offset(max(0,offset)).limit(max(1,min(limit,200))).all())
    return [{'id':notification.id,'user_id':user.id,'user_name':user.name,'user_email':user.email,'title':notification.title,'message':notification.message,'is_read':notification.is_read,'created_at':notification.created_at} for notification,user in rows]
@router.get('/disease-analytics')
def analytics(db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    total=db.query(func.count(DiseaseScan.id)).scalar() or 0
    distribution=[{'disease':d,'count':c} for d,c in db.query(DiseaseScan.predicted_disease,func.count(DiseaseScan.id)).group_by(DiseaseScan.predicted_disease).order_by(func.count(DiseaseScan.id).desc()).all()]
    crop_rows=db.query(Crop.crop_name,func.count(DiseaseScan.id)).join(DiseaseScan,DiseaseScan.crop_id==Crop.id,isouter=True).group_by(Crop.crop_name).order_by(func.count(DiseaseScan.id).desc()).all()
    confidence=[{'band':'<0.50','count':db.query(func.count(DiseaseScan.id)).filter(DiseaseScan.confidence<.5).scalar() or 0},{'band':'0.50-0.75','count':db.query(func.count(DiseaseScan.id)).filter(DiseaseScan.confidence>=.5,DiseaseScan.confidence<.75).scalar() or 0},{'band':'>=0.75','count':db.query(func.count(DiseaseScan.id)).filter(DiseaseScan.confidence>=.75).scalar() or 0}]
    daily=db.query(func.date(DiseaseScan.created_at),func.count(DiseaseScan.id)).group_by(func.date(DiseaseScan.created_at)).order_by(func.date(DiseaseScan.created_at).desc()).limit(90).all()
    weekly=db.query(func.date_trunc('week',DiseaseScan.created_at),func.count(DiseaseScan.id)).group_by(func.date_trunc('week',DiseaseScan.created_at)).order_by(func.date_trunc('week',DiseaseScan.created_at).desc()).limit(52).all()
    monthly=db.query(func.date_trunc('month',DiseaseScan.created_at),func.count(DiseaseScan.id)).group_by(func.date_trunc('month',DiseaseScan.created_at)).order_by(func.date_trunc('month',DiseaseScan.created_at).desc()).limit(24).all()
    return {'total_scans':total,'disease_distribution':distribution,'crop_distribution':[{'crop':a,'count':b} for a,b in crop_rows],'confidence_distribution':confidence,'daily_scans':[{'date':str(a),'count':b} for a,b in reversed(daily)],'weekly_scans':[{'week_start':str(a.date() if hasattr(a,'date') else a),'count':b} for a,b in reversed(weekly)],'monthly_scans':[{'month_start':str(a.date() if hasattr(a,'date') else a),'count':b} for a,b in reversed(monthly)]}
@router.get('/model')
def model(request:Request,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    p=Path(settings.model_metadata_path)
    if not p.is_absolute(): p=Path(__file__).resolve().parents[2]/p
    try: metadata=json.loads(p.read_text(encoding='utf-8'))
    except Exception: metadata={'model_name':'EfficientNetB0','version':settings.model_version,'num_classes':0,'classes':[],'status':'MODEL_NOT_INSTALLED'}
    metadata['model_status']='READY' if predictor.model is not None else 'MODEL_NOT_INSTALLED'
    audit(db,admin,'MODEL_VERSION_VIEWED','MODEL',str(metadata.get('version','unknown')),request); db.commit()
    return metadata
@router.get('/model/metrics')
def model_metrics(db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    rows=db.query(ModelVersion).order_by(ModelVersion.created_at.desc()).all()
    if rows: return [{'version':x.version,'model_name':x.model_name,'training_date':x.training_date,'num_classes':x.num_classes,'metrics':x.metrics,'status':x.status} for x in rows]
    p=Path(settings.model_metadata_path)
    if not p.is_absolute(): p=Path(__file__).resolve().parents[2]/p
    try: metadata=json.loads(p.read_text(encoding='utf-8'))
    except Exception: metadata={}
    return [{'version':metadata.get('version',settings.model_version),'model_name':metadata.get('model_name','EfficientNetB0'),'training_date':metadata.get('training_date'),'num_classes':metadata.get('num_classes',0),'metrics':metadata.get('metrics',{}),'status':'READY' if predictor.model is not None else 'MODEL_NOT_INSTALLED'}]
@router.get('/activity')
def activity(limit:int=50,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    return [{'id':x.id,'admin_id':x.admin_id,'action':x.action,'target_type':x.target_type,'target_id':x.target_id,'timestamp':x.timestamp} for x in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(max(1,min(limit,200))).all()]
@router.get('/audit-logs')
def audit_logs(limit:int=100,offset:int=0,db:Session=Depends(get_db),admin:AdminUser=Depends(get_current_admin)):
    return [{'id':x.id,'admin_id':x.admin_id,'action':x.action,'target_type':x.target_type,'target_id':x.target_id,'timestamp':x.timestamp,'ip_address':x.ip_address,'details':x.details} for x in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(max(offset,0)).limit(max(1,min(limit,200))).all()]

