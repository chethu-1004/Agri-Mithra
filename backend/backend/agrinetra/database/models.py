from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, DateTime, Float, Boolean, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def new_id(): return str(uuid4())
def now_utc(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
class User(TimestampMixin, Base):
    __tablename__='users'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    name: Mapped[str]=mapped_column(String(120),nullable=False)
    email: Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
    phone: Mapped[str|None]=mapped_column(String(40))
    password_hash: Mapped[str]=mapped_column(String(255),nullable=False)
    profile_image: Mapped[str|None]=mapped_column(String(1024))
    status: Mapped[str]=mapped_column(String(20),default='ACTIVE',index=True,nullable=False)
    last_login: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class AdminUser(TimestampMixin, Base):
    __tablename__='admin_users'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    name: Mapped[str]=mapped_column(String(120),nullable=False)
    email: Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
    password_hash: Mapped[str]=mapped_column(String(255),nullable=False)
    role: Mapped[str]=mapped_column(String(20),default='ADMIN',nullable=False)
    status: Mapped[str]=mapped_column(String(20),default='ACTIVE',nullable=False)
    last_login: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class Farm(TimestampMixin, Base):
    __tablename__='farms'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    farm_name: Mapped[str]=mapped_column(String(160),nullable=False)
    location: Mapped[str|None]=mapped_column(String(300))
    latitude: Mapped[float|None]=mapped_column(Float)
    longitude: Mapped[float|None]=mapped_column(Float)
    area: Mapped[float|None]=mapped_column(Float)
class Crop(TimestampMixin, Base):
    __tablename__='crops'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    farm_id: Mapped[str]=mapped_column(ForeignKey('farms.id',ondelete='CASCADE'),index=True,nullable=False)
    crop_name: Mapped[str]=mapped_column(String(120),nullable=False)
    variety: Mapped[str|None]=mapped_column(String(120))
    sowing_date: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    expected_harvest_date: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class DiseaseScan(Base):
    __tablename__='disease_scans'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    farm_id: Mapped[str|None]=mapped_column(ForeignKey('farms.id',ondelete='SET NULL'),index=True)
    crop_id: Mapped[str|None]=mapped_column(ForeignKey('crops.id',ondelete='SET NULL'),index=True)
    image_url: Mapped[str|None]=mapped_column(String(1024))
    image_storage_key: Mapped[str|None]=mapped_column(String(255))
    predicted_disease: Mapped[str]=mapped_column(String(240),nullable=False)
    predicted_class: Mapped[str]=mapped_column(String(240),nullable=False)
    confidence: Mapped[float]=mapped_column(Float,nullable=False)
    model_version: Mapped[str]=mapped_column(String(80),nullable=False)
    status: Mapped[str]=mapped_column(String(30),default='SUCCESS',nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class TreatmentRecommendation(Base):
    __tablename__='treatment_recommendations'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    disease_key: Mapped[str]=mapped_column(String(240),index=True,nullable=False)
    symptoms: Mapped[list]=mapped_column(JSON,default=list,nullable=False)
    prevention: Mapped[list]=mapped_column(JSON,default=list,nullable=False)
    treatment: Mapped[list]=mapped_column(JSON,default=list,nullable=False)
    source: Mapped[str|None]=mapped_column(String(300))
class Notification(Base):
    __tablename__='notifications'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    title: Mapped[str]=mapped_column(String(200),nullable=False)
    message: Mapped[str]=mapped_column(Text,nullable=False)
    is_read: Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class WeatherRecord(Base):
    __tablename__='weather_records'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    latitude: Mapped[float]=mapped_column(Float,nullable=False)
    longitude: Mapped[float]=mapped_column(Float,nullable=False)
    payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class ChatSession(Base):
    __tablename__='chat_sessions'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    title: Mapped[str|None]=mapped_column(String(200))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class ChatMessage(Base):
    __tablename__='chat_messages'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    session_id: Mapped[str]=mapped_column(ForeignKey('chat_sessions.id',ondelete='CASCADE'),index=True,nullable=False)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    role: Mapped[str]=mapped_column(String(20),nullable=False)
    content: Mapped[str]=mapped_column(Text,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class AuditLog(Base):
    __tablename__='audit_logs'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    admin_id: Mapped[str]=mapped_column(ForeignKey('admin_users.id',ondelete='CASCADE'),index=True,nullable=False)
    action: Mapped[str]=mapped_column(String(80),nullable=False)
    target_type: Mapped[str|None]=mapped_column(String(80))
    target_id: Mapped[str|None]=mapped_column(String(36))
    ip_address: Mapped[str|None]=mapped_column(String(64))
    details: Mapped[dict|None]=mapped_column(JSON)
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class ModelVersion(Base):
    __tablename__='model_versions'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    version: Mapped[str]=mapped_column(String(80),unique=True,index=True,nullable=False)
    model_name: Mapped[str]=mapped_column(String(120),default='EfficientNetB0',nullable=False)
    training_date: Mapped[str|None]=mapped_column(String(40))
    num_classes: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    metrics: Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    status: Mapped[str]=mapped_column(String(30),default='AVAILABLE',nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class RevokedToken(Base):
    __tablename__='revoked_tokens'
    jti: Mapped[str]=mapped_column(String(36),primary_key=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)

class MarketProduct(TimestampMixin, Base):
    __tablename__='market_products'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    name: Mapped[str]=mapped_column(String(160),nullable=False)
    category: Mapped[str]=mapped_column(String(80),index=True,nullable=False)
    brand: Mapped[str|None]=mapped_column(String(160))
    description: Mapped[str|None]=mapped_column(Text)
    price: Mapped[float]=mapped_column(Float,nullable=False)
    emoji: Mapped[str]=mapped_column(String(16),default='🌱',nullable=False)
    image_storage_key: Mapped[str|None]=mapped_column(String(255))
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,index=True,nullable=False)
    created_by_admin_id: Mapped[str|None]=mapped_column(ForeignKey('admin_users.id',ondelete='SET NULL'),index=True)

class MarketContact(TimestampMixin, Base):
    __tablename__='market_contacts'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    kind: Mapped[str]=mapped_column(String(20),index=True,nullable=False)
    name: Mapped[str]=mapped_column(String(160),nullable=False)
    organization: Mapped[str|None]=mapped_column(String(160))
    interests: Mapped[str|None]=mapped_column(String(300))
    phone: Mapped[str|None]=mapped_column(String(40))
    email: Mapped[str|None]=mapped_column(String(320))
    location: Mapped[str|None]=mapped_column(String(300))
    description: Mapped[str|None]=mapped_column(Text)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,index=True,nullable=False)
    created_by_admin_id: Mapped[str|None]=mapped_column(ForeignKey('admin_users.id',ondelete='SET NULL'),index=True)

class MarketListing(TimestampMixin, Base):
    __tablename__='market_listings'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    crop_name: Mapped[str]=mapped_column(String(120),nullable=False)
    variety: Mapped[str|None]=mapped_column(String(120))
    quantity: Mapped[str]=mapped_column(String(80),nullable=False)
    price: Mapped[float|None]=mapped_column(Float)
    harvest: Mapped[str|None]=mapped_column(String(120))
    location: Mapped[str|None]=mapped_column(String(300))
    grade: Mapped[str|None]=mapped_column(String(40))
    status: Mapped[str]=mapped_column(String(24),default='ACTIVE',index=True,nullable=False)

class MarketOrder(Base):
    __tablename__='market_orders'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    product_id: Mapped[str]=mapped_column(ForeignKey('market_products.id',ondelete='RESTRICT'),index=True,nullable=False)
    quantity: Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    unit_price: Mapped[float]=mapped_column(Float,nullable=False)
    status: Mapped[str]=mapped_column(String(32),default='PENDING_CONFIRMATION',index=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
