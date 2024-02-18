import os

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

eztv_url = os.getenv("EZTV_URL")

debug_mode = os.getenv("DEBUG_MODE", "False") == "True"
debug_processing_limit = int(os.getenv("DEBUG_PROCESSING_LIMIT", 1500))

rate_limit_per_second = int(os.getenv("RATE_LIMIT_PER_SECOND", 60))

postgres_db = os.getenv("POSTGRES_DB")
postgres_host = os.getenv("POSTGRES_HOST")
postgres_password = os.getenv("POSTGRES_PASSWORD")
postgres_port = os.getenv("POSTGRES_PORT")
postgres_user = os.getenv("POSTGRES_USER")
