from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application settings
    APP_NAME: str = "Link-to-Text Ingestion Service"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/link_to_rag"

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # External API Keys & Proxies
    OPENAI_API_KEY: Optional[str] = None
    JINA_API_KEY: Optional[str] = None
    FIRECRAWL_API_KEY: Optional[str] = None
    APIFY_API_TOKEN: Optional[str] = None
    PROXY_URL: Optional[str] = None
    API_KEYS: Optional[str] = None  # Comma-separated list of valid API keys for multi-tenancy auth


    # Chunking & Vector Settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # Circuit Breaker & Retry Settings
    MAX_RETRIES: int = 3
    CIRCUIT_BREAKER_FAILURES: int = 5
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 900  # 15 minutes


settings = Settings()
