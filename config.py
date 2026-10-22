import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load settings from a local .env file (never committed). See .env.example.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:  # python-dotenv not installed: plain environment variables still work
    pass


def _database_url():
    """DATABASE_URL from .env, or the local SQLite file if it isn't set.

    Hosts like Neon give links starting with postgres:// or postgresql://. Newer SQLAlchemy
    reads those as the psycopg (v3) driver, but we install psycopg2, so name it explicitly.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///" + os.path.join(BASE_DIR, "store.db")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # SQLite works instantly for development. To switch to PostgreSQL or MySQL, set DATABASE_URL in .env:
    #   postgresql+psycopg2://user:password@localhost/onlinestore
    #   mysql+pymysql://user:password@localhost/onlinestore
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Hosted databases (e.g. Neon) close idle connections. Check each one before use
    # and replace it after 5 minutes, so a page never fails on a dropped connection.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
