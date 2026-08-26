"""
Configuration and Environment Settings for BharatTrip SSOT Backend.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "BharatTrip SSOT API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DB_URL: str = "sqlite:///./data/ssot.db"
    
    # Security & JWT
    JWT_SECRET: str = "super-secret-key-bharattrip-ssot-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Auth Mode (mock, google, auth0)
    AUTH_MODE: str = "mock"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # LLM API Keys
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Handle DATABASE_URL alias if present
        env_db_url = os.environ.get("DATABASE_URL")
        if env_db_url:
            self.DB_URL = env_db_url


settings = Settings()
