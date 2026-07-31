from sqlalchemy import text

from database.database import engine, Base
from models.model import (
    User,
    Case,
    Layer,
    Feature,
    Comment,
    ImageRecord,
)


def init_database():

    with engine.begin() as conn:

        # Enable PostGIS
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

        print("✓ PostGIS enabled")

        # Development only
        # Drops all existing tables
        Base.metadata.drop_all(bind=conn)

        print("✓ Old tables dropped")

        # Create every table from models.py
        Base.metadata.create_all(bind=conn)

        print("✓ Tables created successfully")


if __name__ == "__main__":
    init_database()