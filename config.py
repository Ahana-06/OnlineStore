import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # SQLite works instantly for development. To switch to PostgreSQL or MySQL, set DATABASE_URL:
    #   postgresql+psycopg2://user:password@localhost/onlinestore
    #   mysql+pymysql://user:password@localhost/onlinestore
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "store.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
