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
    # Remove the hardcoded URL and use environment variable
    redirect_uri: str
    
    # Google API scopes with read and write permissions
    scopes: List[str] = [
        # Gmail - read and send
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        
        # Calendar - read, write and delete
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        
        # Tasks - read, write and manage
        "https://www.googleapis.com/auth/tasks.readonly", 
        "https://www.googleapis.com/auth/tasks"
    ]
    
    class Config:
        env_file = ".env"
        env_prefix = "GOOGLE_"


# Create settings instance
google_settings = GoogleSettings()