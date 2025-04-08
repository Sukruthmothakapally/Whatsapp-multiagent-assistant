from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str
    qdrant_url: str
    qdrant_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
