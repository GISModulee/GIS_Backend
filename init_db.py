import sys

from sqlalchemy import text
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
        with engine.begin() as conn:
            # create_all() creates missing tables but does not add columns
            # to tables that already exist.
            conn.execute(
                text(
                    "ALTER TABLE layers "
                    "ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_layers_file_hash "
                    "ON layers (file_hash)"
                )
            )
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

 