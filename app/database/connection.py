import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def get_database_url() -> str:
    # 1️⃣ If full DATABASE_URL is provided (Production)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # 2️⃣ Otherwise fallback to local development config
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "ai_news_aggregator")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

engine = create_engine(get_database_url(), pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_session():
    return SessionLocal()