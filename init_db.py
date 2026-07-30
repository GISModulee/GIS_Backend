import sys

from sqlalchemy.exc import SQLAlchemyError

from database.database import Base, engine
from models.model import (
    User,
    Case,
    Layer,
    Feature,
    Comment,
    ImageRecord,
)
from utils.logger import logger


def init_tables():
    logger.info("Initializing database tables...")
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        logger.error(
            f"Database table initialization failed: {e}. "
            "Common causes: PostGIS extension not enabled "
            "(run `CREATE EXTENSION IF NOT EXISTS postgis;`), "
            "or DATABASE_URL is unreachable.",
            exc_info=True,
        )
        sys.exit(1)
    logger.info("Database tables initialized successfully.")


if __name__ == "__main__":
    init_tables()
