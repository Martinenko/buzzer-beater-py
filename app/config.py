from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str

    # BuzzerBeater API
    bb_api_url: str = "https://bbapi.buzzerbeater.com"
    bb_api_verify_ssl: bool = False  # Set to False if BB has expired SSL cert

    # Security
    secret_key: str
    encryption_key: str  # Fernet key for encrypting sensitive data at rest
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Redis
    redis_url: str = ""  # Optional Redis URL for pub/sub (local: redis://localhost:6379)

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
