from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from utils.config import settings
from utils.logger import logger


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   
    connect_args={
        "options": "-csearch_path=gis,public"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding a DB session.
    Ensures the session is always closed, and logs (without swallowing)
    any error that occurs while closing it — a failure here shouldn't
    crash the request since the response has likely already been sent,
    but it must not be silently invisible either.
    """
    db = SessionLocal()
    logger.debug("DB session opened")
    try:
        yield db
    finally:
        try:
            db.close()
            logger.debug("DB session closed")
        except SQLAlchemyError as e:
            logger.error(f"Error closing DB session: {e}", exc_info=True)
