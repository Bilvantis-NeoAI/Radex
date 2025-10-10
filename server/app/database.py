from sqlalchemy import create_engine,pool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from dotenv import load_dotenv
import os
load_dotenv()

DB_POOL_SIZE=int(os.getenv("DB_POOL_SIZE"))
DB_MAX_OVERFLOW=int(os.getenv("DB_MAX_OVERFLOW"))
DB_POOL_RECYCLE=int(os.getenv("DB_POOL_RECYCLE"))
DB_POOL_PRE_PING=bool(os.getenv("DB_POOL_PRE_PING"))
DB_POOL_TIMEOUT=int(os.getenv("DB_POOL_TIMEOUT"))

engine = create_engine(
    settings.database_url,
    poolclass=pool.QueuePool,
    pool_size=DB_POOL_SIZE,              # Number of connections in the pool
    max_overflow=DB_MAX_OVERFLOW,        # Extra connections beyond pool_size
    pool_recycle=DB_POOL_RECYCLE,        # Recycle connections every hour (seconds)
    pool_pre_ping=DB_POOL_PRE_PING,      # Check connection health before use
    pool_timeout=DB_POOL_TIMEOUT,        # Timeout for getting a connection (seconds)
    echo=settings.debug                  # Log SQL statements in debug mode
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()