import os

from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)


class ConfigModel(BaseSettings):
    model_config = SettingsConfigDict()

    eztv_url: str = Field(default="https://eztvx.to")
    eztv_showlist_url: str = Field(default="/showlist/")

    rate_limit_per_second: int = Field(default=1)

    debug_mode: bool = Field(default=False)
    debug_processing_limit: int = Field(default=120)

    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="knightcrawler")
    postgres_user: str = Field(default="knightcrawler")
    postgres_password: str = Field(default="password")

    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str = Field(default="password")

    @validator("eztv_url", "eztv_showlist_url", pre=True, allow_reuse=True)
    def ensure_correct_format(cls, v):
        if "eztv_url" in cls.model_fields and not v.endswith("/"):
            return v.rstrip("/")
        if "eztv_showlist_url" in cls.model_fields:
            v = v.rstrip("/").lstrip("/")
            return f"/{v}/"
        return v


config = ConfigModel()

# The validators ensure the URLs are formatted correctly,
# and the use of Field with env parameter makes sure the environment variables are used if present.
