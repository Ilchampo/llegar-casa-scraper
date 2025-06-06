"""Global configuration management using Pydantic BaseSettings."""
from .constants import Environment
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Global application settings using Pydantic BaseSettings.
    
    All settings can be overridden via environment variables.
    Example: ENVIRONMENT=production will override the default development setting.
    """
    
    APP_NAME: str = "LlegarCasa Scrapper"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = True
    SHOW_DOCS: bool = True
    
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    SCRAPER_HEADLESS_MODE: bool = True
    SCRAPER_SAVE_SCREENSHOTS: bool = False
    SCRAPER_DEBUG_MODE: bool = False
    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
