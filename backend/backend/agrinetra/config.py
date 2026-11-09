from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator,model_validator
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    app_name: str = 'Agri Mitra API'
    environment: str = 'development'
    database_url: str = 'postgresql+psycopg://agrinetra@127.0.0.1:5433/agrinetra'
    jwt_secret: str = 'change-this-development-secret-to-a-long-random-value'
    jwt_algorithm: str = 'HS256'
    access_token_minutes: int = 60
    prediction_threshold: float = 0.60
    model_path: str = 'ml_models/efficientnetb0_agrinetra_v1.keras'
    class_labels_path: str = 'ml_models/class_labels_v1.json'
    model_metadata_path: str = 'ml_models/model_metadata_v1.json'
    upload_dir: str = 'uploads'
    max_upload_mb: int = 10
    user_frontend_url: str = 'http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5173,http://localhost:5173'
    admin_frontend_url: str = ''
    weather_provider: str = 'open-meteo'
    weather_api_key: str = ''
    chatbot_provider: str = 'ollama'
    chatbot_api_key: str = ''
    chatbot_base_url: str = ''
    chatbot_model: str = ''
    openai_api_key: str = ''
    openai_base_url: str = ''
    openai_model: str = ''
    chatbot_timeout_seconds: float = 30
    chatbot_requests_per_minute: int = 20
    chatbot_history_messages: int = 12
    ollama_base_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen2.5:3b'
    ollama_timeout_seconds: float = 90
    web_search_enabled: bool = False
    tavily_api_key: str = ''
    tavily_timeout_seconds: float = 12
    ai_max_request_bytes: int = 32768
    agri_rag_enabled: bool = False
    agri_rag_documents_dir: str = 'knowledge/agriculture'
    agri_rag_index_path: str = 'knowledge/agriculture_index.json'
    openai_embedding_model: str = 'text-embedding-3-small'
    storage_provider: str = 'local'
    storage_bucket: str = ''
    model_version: str = 'v1'
    @field_validator('prediction_threshold')
    @classmethod
    def threshold_range(cls, value):
        if not 0 <= value <= 1: raise ValueError('PREDICTION_THRESHOLD must be between 0 and 1')
        return value
    @model_validator(mode='after')
    def production_secret(self):
        if self.environment.lower()=='production' and (len(self.jwt_secret)<32 or self.jwt_secret.startswith('change-this-')):
            raise ValueError('Set a unique JWT_SECRET of at least 32 characters in production.')
        return self
settings=Settings()
