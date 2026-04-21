from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # Security
    secret_key: str = ""
    allowed_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

@lru_cache
def get_settings() -> Settings:
    return Settings()