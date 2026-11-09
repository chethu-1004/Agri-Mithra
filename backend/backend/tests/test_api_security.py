import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from PIL import Image
from agrinetra.database.models import Base,AdminUser,DiseaseScan,new_id
from agrinetra.database.connection import get_db
from agrinetra.auth.password import hash_password
from agrinetra.disease_detection.model_loader import ModelUnavailable,predictor
from agrinetra.species_detection.predictor import predictor as species_predictor
from agrinetra.config import settings
from main import app

@pytest.fixture()
def client(monkeypatch,tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    TestingSession=sessionmaker(bind=engine,autoflush=False,autocommit=False,expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path/'uploads'))
    monkeypatch.setattr(predictor,'load',lambda:None)
    monkeypatch.setattr(species_predictor,'load',lambda:None)
    def override_db():
        db=TestingSession()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db]=override_db
    app.state.testing_session_factory=TestingSession
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()
def register(client,email):
    r=client.post('/api/auth/register',json={'name':'Farmer','email':email,'password':'safe-password-123'}); assert r.status_code==201
    t=client.post('/api/auth/login',json={'email':email,'password':'safe-password-123'}); assert t.status_code==200
    return {'Authorization':'Bearer '+t.json()['access_token']}
def seed_admin(client):
    factory=app.state.testing_session_factory; db=factory()
    try:
        db.add(AdminUser(name='Admin',email='admin@example.com',password_hash=hash_password('admin-password-123'),role='ADMIN',status='ACTIVE')); db.commit()
    finally: db.close()
    response=client.post('/api/admin/auth/login',json={'email':'admin@example.com','password':'admin-password-123'})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}
def png_bytes():
    stream=io.BytesIO(); Image.new('RGB',(16,16),(30,160,40)).save(stream,format='PNG'); return stream.getvalue()
def test_user_cannot_read_another_users_farm_or_crop(client):
    a=register(client,'a@example.com'); b=register(client,'b@example.com')
    farm=client.post('/api/farms',headers=b,json={'farm_name':'Private farm'}).json()
    assert client.get('/api/farms/'+farm['id'],headers=a).status_code==404
    assert client.get('/api/farms/'+farm['id'],headers=b).status_code==200
    assert client.post('/api/crops',headers=a,json={'farm_id':farm['id'],'crop_name':'Tomato'}).status_code==404
def test_registration_login_and_invalid_password(client):
    headers=register(client,'farmer@example.com')
    assert client.get('/api/users/me',headers=headers).status_code==200
    assert client.post('/api/auth/login',json={'email':'farmer@example.com','password':'wrong-password'}).status_code==401
def test_admin_login_and_role_authorization(client):
    user=register(client,'ordinary@example.com'); admin=seed_admin(client)
    assert client.get('/api/admin/dashboard').status_code==401
    assert client.get('/api/admin/dashboard',headers=user).status_code==403
    assert client.get('/api/admin/dashboard',headers=admin).status_code==200
def test_user_response_never_contains_password_hash(client):
    headers=register(client,'profile@example.com'); response=client.get('/api/users/me',headers=headers)
    assert response.status_code==200
    assert 'password_hash' not in response.text and 'password' not in response.text.lower()
def test_invalid_and_corrupted_images_are_rejected(client,monkeypatch):
    headers=register(client,'image@example.com')
    for route in ('/api/disease/predict','/api/species/predict'):
        assert client.post(route,headers=headers).status_code==422
        for payload in (b'not an image',b''):
            response=client.post(route,headers=headers,files={'file':('bad.jpg',payload,'image/jpeg')})
            assert response.status_code==400
def test_valid_prediction_and_private_scan_image(client,monkeypatch):
    owner=register(client,'scan-owner@example.com'); other=register(client,'scan-other@example.com')
    monkeypatch.setattr(predictor,'predict',lambda path:('Tomato_Early_blight',.94))
    response=client.post('/api/disease/predict',headers=owner,files={'file':('leaf.png',png_bytes(),'image/png')})
    assert response.status_code==200 and response.json()['status']=='success'
    scan_id=response.json()['scan_id']; image_url=response.json()['scan_id']
    assert client.get(f'/api/disease/history/{scan_id}/image',headers=owner).status_code==200
    assert client.get(f'/api/disease/history/{scan_id}/image',headers=other).status_code==404
    assert client.get(f'/api/disease/history/{scan_id}',headers=other).status_code==404
    assert client.get(f'/api/disease/history/{scan_id}',headers=owner).json()['image_url'].endswith('/image')
def test_low_confidence_is_saved_as_uncertain(client,monkeypatch):
    headers=register(client,'uncertain@example.com')
    monkeypatch.setattr(predictor,'predict',lambda path:('Tomato___Late_blight',.42))
    response=client.post('/api/disease/predict',headers=headers,files={'file':('leaf.png',png_bytes(),'image/png')})
    assert response.status_code==200 and response.json()['status']=='uncertain'
    history=client.get('/api/disease/history',headers=headers).json()
    assert history[0]['status']=='UNCERTAIN'

def test_species_prediction_includes_analysis_and_server_confidence_status(client,monkeypatch):
    headers=register(client,'species-analysis@example.com')
    monkeypatch.setattr(species_predictor,'predict',lambda path:{
        'species':'Pongamia Pinnata (P7)',
        'predicted_class':'Pongamia Pinnata (P7)',
        'confidence':0.55,
        'top_predictions':[{'class':'Pongamia Pinnata (P7)','confidence':0.55}],
    })
    monkeypatch.setattr(predictor,'predict',lambda path:(_ for _ in ()).throw(ModelUnavailable('not installed')))
    response=client.post('/api/species/predict',headers=headers,files={'file':('leaf.png',png_bytes(),'image/png')})
    assert response.status_code==200
    body=response.json()
    assert body['status']=='success' and body['scan_id']
    prediction=body['prediction']
    assert prediction['species']=='Pongamia Pinnata (P7)'
    assert prediction['status']=='UNCERTAIN' and prediction['is_confident'] is False
    analysis=prediction['analysis']
    assert analysis['plant']['status']=='uncertain'
    assert analysis['plant']['prediction_confidence']==pytest.approx(0.55)
    assert analysis['health']['score_percent'] is None
    assert analysis['water_status']['water_content_percent'] is None
    assert analysis['water_status']['moisture_assessment']=='uncertain'
    assert analysis['water_status']['soil_moisture']['status']=='not_measured'
    assert analysis['disease']['status']=='not_configured'
    assert analysis['recommendation']['evidence_quality']=='insufficient'

def test_species_human_result_skips_disease_prediction(client,monkeypatch):
    headers=register(client,'human-image@example.com')
    monkeypatch.setattr(species_predictor,'predict',lambda path:{
        'human_detected':True,
        'analysis_type':'human',
        'predicted_class':'Human detected',
        'confidence':None,
    })
    def unexpected_disease_prediction(path):
        raise AssertionError('Disease prediction must not run for a human image.')
    monkeypatch.setattr(predictor,'predict',unexpected_disease_prediction)
    response=client.post('/api/species/predict',headers=headers,files={'file':('person.png',png_bytes(),'image/png')})
    assert response.status_code==200
    analysis=response.json()['prediction']['analysis']
    assert analysis['plant']['status']=='human_detected'
    assert analysis['plant']['name'] is None
    assert analysis['disease']['status']=='not_applicable'
    assert analysis['health']['condition']=='not_applicable'
    assert analysis['water_status']['moisture_assessment']=='not_applicable'
    assert analysis['water_status']['soil_moisture']['value'] is None
