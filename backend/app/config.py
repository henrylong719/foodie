"""Application settings, loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "supermarket_assistant"

    # CORS — the Next.js frontend origin(s)
    frontend_origins: list[str] = ["http://localhost:3000"]

    # App
    app_name: str = "AI Phone Call Sales Assistant"
    debug: bool = False


settings = Settings()
