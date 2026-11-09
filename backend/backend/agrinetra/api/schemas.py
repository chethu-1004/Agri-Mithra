from datetime import datetime
from typing import Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
class UserRegister(BaseModel):
    name: str=Field(min_length=1,max_length=120)
    email: EmailStr
    phone: str|None=Field(default=None,max_length=40)
    password: str=Field(min_length=10,max_length=128)
class LoginRequest(BaseModel): email: EmailStr; password: str
class FarmerLoginRequest(BaseModel): identifier:str|None=Field(default=None,min_length=1,max_length=320); email:EmailStr|None=None; phone:str|None=Field(default=None,max_length=40); password:str=Field(min_length=1,max_length=128)
class PasswordChange(BaseModel): current_password:str=Field(min_length=1,max_length=128); new_password:str=Field(min_length=10,max_length=128)
class AdminPasswordReset(BaseModel): new_password:str=Field(min_length=10,max_length=128)
class TokenResponse(BaseModel): access_token: str; token_type: str='bearer'; role: str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str; name:str; email:str; phone:str|None=None; profile_image:str|None=None; status:str; created_at:datetime; last_login:datetime|None=None
class UserUpdate(BaseModel): name:str|None=Field(default=None,min_length=1,max_length=120); phone:str|None=Field(default=None,max_length=40)
class FarmIn(BaseModel): farm_name:str=Field(min_length=1,max_length=160); location:str|None=None; latitude:float|None=Field(default=None,ge=-90,le=90); longitude:float|None=Field(default=None,ge=-180,le=180); area:float|None=Field(default=None,gt=0)
class FarmOut(FarmIn): model_config=ConfigDict(from_attributes=True); id:str; user_id:str; created_at:datetime; updated_at:datetime
class CropIn(BaseModel): farm_id:str; crop_name:str=Field(min_length=1,max_length=120); variety:str|None=None; sowing_date:datetime|None=None; expected_harvest_date:datetime|None=None
class CropOut(CropIn): model_config=ConfigDict(from_attributes=True); id:str; user_id:str; created_at:datetime; updated_at:datetime
class StatusUpdate(BaseModel): status:str=Field(pattern='^(ACTIVE|DISABLED)$')
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default='English', min_length=2, max_length=12)
    session_id: str | None = Field(default=None, min_length=1, max_length=36)
    scan_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator('message')
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Message must not be blank.')
        return value

    @field_validator('language')
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip().casefold().replace('_', '-')
        languages = {
            'english': 'English', 'en': 'English', 'en-in': 'English',
            'kannada': 'Kannada', 'kn': 'Kannada', 'kn-in': 'Kannada',
            'tamil': 'Tamil', 'ta': 'Tamil', 'ta-in': 'Tamil',
            'telugu': 'Telugu', 'te': 'Telugu', 'te-in': 'Telugu',
            'hindi': 'Hindi', 'hi': 'Hindi', 'hi-in': 'Hindi',
        }
        language = languages.get(normalized)
        if not language:
            raise ValueError('Choose English, Kannada, Tamil, Telugu, or Hindi.')
        return language


class ChatScanIn(BaseModel):
    scan_id: str = Field(min_length=1, max_length=36)
    session_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator('scan_id', 'session_id')
    @classmethod
    def strip_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError('Identifier must not be blank.')
        return value


class AiHealthMeasurementIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    metric: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=0, le=100, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=24)
    source: str = Field(min_length=1, max_length=160)
    method: str = Field(min_length=1, max_length=160)
    measured_at: datetime | None = None
    validation_status: Literal['validated', 'unverified'] = 'unverified'

    @field_validator('metric', 'unit', 'source', 'method')
    @classmethod
    def strip_measurement_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Measurement details cannot be blank.')
        return value

    @model_validator(mode='after')
    def validated_measurement_has_provenance(self):
        if self.validation_status == 'validated' and (not self.source or not self.method or self.measured_at is None):
            raise ValueError('A validated measurement requires a source, method, and measurement time.')
        return self


class AiPlantContextIn(BaseModel):
    """Optional client-reported context; the API labels it as unverified."""

    model_config = ConfigDict(extra='forbid')

    crop_name: str | None = Field(default=None, max_length=120, validation_alias=AliasChoices('crop_name', 'crop'))
    predicted_disease: str | None = Field(default=None, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confidence_type: Literal['uncalibrated_model_score', 'calibrated_probability'] = 'uncalibrated_model_score'
    validated_health_measurements: list[AiHealthMeasurementIn] = Field(default_factory=list, max_length=8)

    @field_validator('crop_name', 'predicted_disease')
    @classmethod
    def strip_plant_labels(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AiChatIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default='English', min_length=2, max_length=48)
    session_id: str | None = Field(default=None, min_length=1, max_length=36)
    scan_id: str | None = Field(default=None, min_length=1, max_length=36)
    plant_context: AiPlantContextIn | None = Field(default=None, validation_alias=AliasChoices('plant_context', 'context'))

    @field_validator('message')
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Message must not be blank.')
        return value

    @field_validator('language')
    @classmethod
    def validate_language_label(cls, value: str) -> str:
        import re

        value = value.strip()
        if not re.fullmatch(r'[\w][\w .\-\']{1,47}', value, flags=re.UNICODE):
            raise ValueError('Choose a language name using letters, spaces, apostrophes, or hyphens.')
        return value

    @field_validator('session_id', 'scan_id')
    @classmethod
    def strip_chat_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError('Identifier must not be blank.')
        return value


class AiSourceOut(BaseModel):
    id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2048)


class AiCitationOut(BaseModel):
    quote: str = Field(min_length=1, max_length=1000)
    source_ids: list[int] = Field(min_length=1, max_length=8)


class AiChatOut(BaseModel):
    success: bool = True
    session_id: str
    answer: str
    language: str
    sources: list[AiSourceOut] = Field(default_factory=list)
    citations: list[AiCitationOut] = Field(default_factory=list)
    search_used: bool = False


class AiHealthOut(BaseModel):
    status: Literal['ok', 'not_configured', 'unavailable', 'model_missing']
    provider: Literal['ollama'] = 'ollama'
    model: str
    configured: bool
    llm_enabled: bool
    reachable: bool = False
    model_available: bool = False
    web_search_enabled: bool = False
class MarketProductIn(BaseModel):
    name:str=Field(min_length=1,max_length=160)
    category:str=Field(min_length=1,max_length=80)
    brand:str|None=Field(default=None,max_length=160)
    description:str|None=Field(default=None,max_length=2000)
    price:float=Field(gt=0,le=100000000)
    emoji:str=Field(default='🌱',max_length=16)
    is_active:bool=True
class MarketProductStatus(BaseModel): is_active:bool
class MarketContactIn(BaseModel):
    kind:Literal['SUPPLIER','BUYER']
    name:str=Field(min_length=1,max_length=160)
    organization:str|None=Field(default=None,max_length=160)
    interests:str|None=Field(default=None,max_length=300)
    phone:str|None=Field(default=None,max_length=40)
    email:str|None=Field(default=None,max_length=320)
    location:str|None=Field(default=None,max_length=300)
    description:str|None=Field(default=None,max_length=2000)
    is_active:bool=True
class MarketContactStatus(BaseModel): is_active:bool
class MarketListingIn(BaseModel):
    crop_name:str=Field(min_length=1,max_length=120)
    variety:str|None=Field(default=None,max_length=120)
    quantity:str=Field(min_length=1,max_length=80)
    price:float|None=Field(default=None,gt=0,le=100000000)
    harvest:str|None=Field(default=None,max_length=120)
    location:str|None=Field(default=None,max_length=300)
    grade:str|None=Field(default=None,max_length=40)
class MarketOrderIn(BaseModel): product_id:str=Field(min_length=1,max_length=36); quantity:int=Field(default=1,ge=1,le=10000)
