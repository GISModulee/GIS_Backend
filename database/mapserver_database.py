from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from utils.config import settings


MapServerBase = declarative_base()

mapserver_engine = None
MapServerSessionLocal = None

if settings.MAPSERVER_DATABASE_URL:
    mapserver_engine = create_engine(settings.MAPSERVER_DATABASE_URL, pool_pre_ping=True)
    MapServerSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mapserver_engine)


def get_mapserver_db():
    return MapServerSessionLocal() if MapServerSessionLocal is not None else None
