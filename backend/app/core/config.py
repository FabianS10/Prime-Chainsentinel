from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field(default="Prime ChainSentinel", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS")
    market_data_provider: str = Field(default="yahoo", alias="MARKET_DATA_PROVIDER")
    alpha_vantage_api_key: str | None = Field(default=None, alias="ALPHA_VANTAGE_API_KEY")
    finnhub_api_key: str | None = Field(default=None, alias="FINNHUB_API_KEY")
    market_cache_ttl_minutes: int = Field(default=60, alias="MARKET_CACHE_TTL_MINUTES")

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
