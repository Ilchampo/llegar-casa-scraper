"""Scraper module configuration."""

from pydantic_settings import BaseSettings


class ScraperConfig(BaseSettings):
    """Scraper-specific configuration."""
    
    HEADLESS_MODE: bool = True
    BROWSER_TIMEOUT: int = 30000
    PAGE_TIMEOUT: int = 20000
    
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5
    ENABLE_STEALTH: bool = True
    
    SAVE_SCREENSHOTS: bool = False
    DEBUG_MODE: bool = False
    
    class Config:
        env_prefix = "SCRAPER_"
        case_sensitive = True


scraper_settings = ScraperConfig()
