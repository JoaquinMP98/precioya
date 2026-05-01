from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///./precioya.db"
    admin_api_key: str = "changeme"
    log_level: str = "INFO"
    playwright_headless: bool = True
    playwright_enabled: bool = True

    scraper_timeout: float = 10.0
    cache_ttl_hours: int = 24
    port: int = 8000


settings = Settings()
