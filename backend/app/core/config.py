from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Google Ads Optimizer"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "postgresql+asyncpg://optimizer:optimizer@localhost:5432/ads_optimizer"
    JWT_SECRET: str = "dev-secret"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    CORS_ORIGIN_REGEX: str = (
        r"^https?://(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?$"
    )
    FRONTEND_URL: str = "http://localhost:5173"
    RAILWAY_PUBLIC_DOMAIN: str | None = None
    RAILWAY_VOLUME_MOUNT_PATH: str | None = None
    GOOGLE_OAUTH_STORE_PATH: str | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: AnyHttpUrl | str = "http://localhost:8000/api/v1/auth/google/callback"
    GOOGLE_ADS_DEVELOPER_TOKEN: str | None = None
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str | None = None
    GOOGLE_ADS_CUSTOMER_ID: str | None = None
    GOOGLE_ADS_CUSTOMER_IDS: str | None = None
    ENABLE_LIVE_GOOGLE_ADS_MUTATIONS: bool = False
    GOOGLE_SEARCH_API_KEY: str | None = None
    GOOGLE_SEARCH_ENGINE_ID: str | None = None
    AFFILIATE_RESEARCH_MAX_RESULTS: int = 5
    ENABLE_HEADLESS_BROWSER: bool = True
    PAGE_READER_HTTP_TIMEOUT_SECONDS: float = 8.0
    PAGE_READER_BROWSER_TIMEOUT_MS: int = 12000
    PAGE_READER_SETTLE_MS: int = 750
    PAGE_READER_MIN_WORDS: int = 80
    PAGE_READER_MIN_CONFIDENCE: int = 55
    PAGE_READER_MAX_HTML_CHARS: int = 500000

    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    AI_PROVIDER: str = "openai"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}
        return value

    @field_validator("ENABLE_LIVE_GOOGLE_ADS_MUTATIONS", mode="before")
    @classmethod
    def parse_live_mutations(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @field_validator("ENABLE_HEADLESS_BROWSER", mode="before")
    @classmethod
    def parse_headless_browser(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @model_validator(mode="after")
    def use_railway_public_url(self):
        """Use the generated Railway domain when explicit public URLs are absent."""
        domain = (self.RAILWAY_PUBLIC_DOMAIN or "").strip().strip("/")
        if not domain:
            return self
        public_origin = f"https://{domain}"
        if self.FRONTEND_URL == "http://localhost:5173":
            self.FRONTEND_URL = public_origin
        if str(self.GOOGLE_REDIRECT_URI) == "http://localhost:8000/api/v1/auth/google/callback":
            self.GOOGLE_REDIRECT_URI = f"{public_origin}/api/v1/auth/google/callback"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
