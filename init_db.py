

import argparse
import sys
from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from database.database import Base, engine
from models import model  # noqa: F401  registers every table on Base.metadata
from utils.config import settings
from utils.logger import logger

ALEMBIC_INI = "alembic.ini"
ALEMBIC_VERSION_TABLE = "alembic_version"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}
POSTGIS_OWNED_TABLES = {"spatial_ref_sys", "geography_columns", "geometry_columns", "raster_columns"}


def _target_host() -> str:
    return urlparse(settings.DATABASE_URL).hostname or ""


def _current_revision() -> str | None:
    with engine.connect() as conn:
        if not inspect(conn).has_table(ALEMBIC_VERSION_TABLE):
            return None
        return conn.execute(
            sa.text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")
        ).scalar()


def _is_empty() -> bool:
    """True when the database holds no application tables at all.

    Checked before the PostGIS extension is enabled, and ignores the
    tables the extension brings with it, so a server that already has
    PostGIS installed still counts as empty.
    """
    with engine.connect() as conn:
        existing = set(inspect(conn).get_table_names())
    return not (existing - {ALEMBIC_VERSION_TABLE} - POSTGIS_OWNED_TABLES)


def _ensure_postgis() -> None:
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    logger.info("PostGIS extension present")


def _alembic(action, *args) -> None:
    """Run an Alembic command.

    migrations/env.py calls fileConfig(), which disables loggers that
    already exist, so the "backend" logger goes quiet for the rest of the
    process unless it is re-enabled afterwards.
    """
    action(Config(ALEMBIC_INI), *args)
    logger.disabled = False


def _create_from_models() -> None:
    Base.metadata.create_all(bind=engine)
    _alembic(command.stamp, "head")
    logger.info(
        "Created %d table(s) from models and stamped %s",
        len(Base.metadata.tables),
        _current_revision(),
    )


def _drop_everything() -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {ALEMBIC_VERSION_TABLE} CASCADE"))
        Base.metadata.drop_all(bind=conn)
    logger.info("Dropped existing tables and migration history")


def bootstrap(force_reset: bool = False) -> None:
    if force_reset:
        _drop_everything()

    # Decided before the extension is enabled: enabling PostGIS creates
    # spatial_ref_sys, which would make the database look non-empty.
    empty = _is_empty()
    _ensure_postgis()

    if empty:
        _create_from_models()
        return

    before = _current_revision()
    _alembic(command.upgrade, "head")
    logger.info("Migrated %s -> %s", before or "<unstamped>", _current_revision())


def reset_database(force: bool) -> None:
    host = _target_host()
    if host not in LOCAL_HOSTS and not force:
        logger.error(
            "Refusing to drop every table on non-local database %r. This "
            "deletes all data. Re-run with --force if that is intended.",
            host,
        )
        sys.exit(1)
    logger.warning("Resetting every table on %r", host)
    bootstrap(force_reset=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or migrate the GIS Backend database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop every table and all data, then rebuild at head.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --reset against a non-local database.",
    )
    args = parser.parse_args()

    logger.info("Target database host: %r", _target_host())

    if args.reset:
        reset_database(force=args.force)
    else:
        bootstrap()


if __name__ == "__main__":
    main()
