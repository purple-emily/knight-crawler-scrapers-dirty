import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

class ConfigModel(BaseModel):
    eztv_url: str = Field(default="https://eztvx.to", env="EZTV_URL")
    eztv_showlist_url: str = Field(default="/showlist/", env="EZTV_SHOWLIST_URL")
    rate_limit_per_second: int = Field(default=1, env="RATE_LIMIT_PER_SECOND")
    debug_mode: bool = Field(default=False, env="DEBUG_MODE")
    debug_processing_limit: int = Field(default=120, env="DEBUG_PROCESSING_LIMIT")
    postgres_host: str = Field(default="192.168.1.252", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="knightcrawler", env="POSTGRES_DB")
    postgres_user: str = Field(default="knightcrawler", env="POSTGRES_USER")
    postgres_password: str = Field(default="password", env="POSTGRES_PASSWORD")
    redis_host: str = Field(default="192.168.1.252", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: str = Field(default="password", env="REDIS_PASSWORD")

    @validator('eztv_url', 'eztv_showlist_url', pre=True, allow_reuse=True)
    def ensure_correct_format(cls, v):
        if 'eztv_url' in cls.__fields__ and not v.endswith("/"):
            return v.rstrip("/")
        if 'eztv_showlist_url' in cls.__fields__:
            v = v.rstrip("/").lstrip("/")
            return f"/{v}/"
        return v

config = ConfigModel()

# The validators ensure the URLs are formatted correctly,
# and the use of Field with env parameter makes sure the environment variables are used if present.
