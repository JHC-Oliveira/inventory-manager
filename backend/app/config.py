from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# __file__ is the absolute path of config.py itself
# .parent gives us the app/ folder
# .parent again gives us the backend/ folder
# then we add .env to get backend/.env
ENV_FILE = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    # App
    app_name: str = "Inventory Manager"
    app_env: str = "development"
    debug: bool = False

    # Database
    database_url: str = ""

    # Security CORS
    secret_key: str = ""    

    allowed_origins: str = "http://localhost:3000"

    # JWT — added in Phase 2
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Redis — added in Phase 2
    redis_url: str = "redis://redis:6379/0"
    
    # RabbitMQ — added in Phase 4
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def check_required_fields(self) -> "Settings":
        missing = []
        
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.secret_key:
            missing.append("SECRET_KEY")
        if not self.rabbitmq_url:
            missing.append("RABBITMQ_URL")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        return self
    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

@lru_cache
def get_settings() -> Settings:
    return Settings()