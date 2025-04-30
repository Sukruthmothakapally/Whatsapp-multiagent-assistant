from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
