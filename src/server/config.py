from pydantic_settings import BaseSettings
from typing import Optional, List
from pathlib import Path

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()


class GoogleSettings(BaseSettings):
    """Configuration settings for Google API integration"""
    client_secrets_file: str = str(BASE_DIR / "client_secret.json")
    token_file: str = str(BASE_DIR / "google_token.pickle")
    redirect_uri: str = "https://7420-73-231-49-218.ngrok-free.app/oauth/callback"
    
    # Google API scopes
    scopes: List[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/tasks.readonly"
    ]
    
    class Config:
        env_file = ".env"
        env_prefix = "GOOGLE_"


# Create settings instance
google_settings = GoogleSettings()