from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigModel(BaseSettings):  # pragma: no cover
    model_config = SettingsConfigDict(env_file=".env")

    eztv_base_url: str = Field(default="https://eztvx.to")
    eztv_showlist_route: str = Field(default="/showlist/")

    rate_limit_per_second: int = Field(default=3)

    batch_size: int = Field(default=25)

    debug_mode: bool = Field(default=False)
    debug_processing_limit: int = Field(default=120)

    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="knightcrawler")
    postgres_user: str = Field(default="knightcrawler")
    postgres_password: str = Field(default="password")

    rabbit_uri: str = Field(default="amqp://guest:guest@rabbitmq:5672/?heartbeat=30")

    # Knight Crawler specific
    torrent_source: str = Field(default="EZTV")
    ingested_torrents_table: str = Field(default="public.ingested_torrents")

    @field_validator("eztv_base_url")
    @classmethod
    def eztv_url_must_not_have_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("eztv_showlist_route")
    @classmethod
    def eztv_showlist_url_must_have_leading_and_trailing_slash(cls, v: str) -> str:
        return f"/{v.rstrip('/').lstrip('/')}/"


config = ConfigModel()
