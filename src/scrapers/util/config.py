import os

from dotenv import load_dotenv

dotenv_path: str = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

eztv_url: str = os.getenv("EZTV_URL", "https://eztvx.to").rstrip("/")
eztv_showlist_url: str = os.getenv("EZTV_SHOWLIST_URL", "/showlist/")
# Fix user error: ensure a leading slash
if not eztv_showlist_url.startswith("/"):
    eztv_showlist_url = f"/{eztv_showlist_url}"
# Fix user error: ensure a trailing slash
if not eztv_showlist_url.endswith("/"):
    eztv_showlist_url = f"{eztv_showlist_url}/"

debug_mode: bool = os.getenv("DEBUG_MODE", "False") == "True"
debug_processing_limit: int = int(os.getenv("DEBUG_PROCESSING_LIMIT", 150))

rate_limit_per_second: int = int(os.getenv("RATE_LIMIT_PER_SECOND", 1))

postgres_db = os.getenv("POSTGRES_DB")
postgres_host = os.getenv("POSTGRES_HOST")
postgres_password = os.getenv("POSTGRES_PASSWORD")
postgres_port = os.getenv("POSTGRES_PORT")
postgres_user = os.getenv("POSTGRES_USER")
