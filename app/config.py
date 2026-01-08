from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str

    # BuzzerBeater API
    bb_api_url: str = "https://bbapi.buzzerbeater.com"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # CORS - include both local and production origins
    cors_origins: list[str] = [
        "http://localhost:4200",
        "https://bbscout.me",
        "https://www.bbscout.me",
        "https://mellow-truffle-30faa7.netlify.app",
    ]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
