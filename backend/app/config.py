from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    openai_api_key: str = ""
    google_api_key: str = ""
    github_token: str = ""
    database_url: str = "sqlite:///./pipelinemedic.db"
    chroma_persist_dir: str = "./chroma_db"
    ai_provider: str = "mock"  # "openai", "google", or "mock"
    max_log_size_mb: int = 10
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:80", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
