from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Okta
    OKTA_CLIENT_ID: str
    OKTA_CLIENT_SECRET: str
    OKTA_DOMAIN: str
    OKTA_REDIRECT_URI: str
    OKTA_API_TOKEN: str

    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "documents"
    minio_secure: bool = False
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    
    # OpenAI
    openai_api_key: str

    # Firebase
    firebase_admin_sdk_json: Optional[str] = None
    
    # App
    app_name: str = "RAG RBAC System"
    debug: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()