from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")

revision = "20260928_09"
down_revision = "20260928_08"
branch_labels = None
depends_on = None

SCHEMA = None

TABLE = "emails"
PK_NAME = "pk_emails"
IP_TYPE_COLUMN = "ip_type"
BACKFILL_VALUE = "origin"
OLD_KEY = ["case_id", "email_id", "ip"]
NEW_KEY = ["case_id", "email_id", "ip", "ip_type"]


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _insp():
    return sa.inspect(op.get_bind())


def _qualified(table: str) -> str:
    return f"{SCHEMA}.{table}" if SCHEMA else table


def _set_primary_key(inspector, columns):
    existing = inspector.get_pk_constraint(TABLE, schema=SCHEMA)
    if existing and existing.get("name"):
        op.drop_constraint(existing["name"], TABLE, type_="primary", **_schema_args())
    op.create_primary_key(PK_NAME, TABLE, columns, **_schema_args())


def _backfill_ip_type(bind) -> int:
    result = bind.execute(
        sa.text(
            f"""
            UPDATE {_qualified(TABLE)}
            SET {IP_TYPE_COLUMN} = :value
            WHERE {IP_TYPE_COLUMN} IS NULL
            """
        ),
        {"value": BACKFILL_VALUE},
    )
    return result.rowcount or 0


def upgrade():
    inspector = _insp()
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return

    bind = op.get_bind()
    filled = _backfill_ip_type(bind)
    if filled:
        logger.info(
            "Backfilled %s row(s) of %s.%s to %r so the role can join the key",
            filled,
            _qualified(TABLE),
            IP_TYPE_COLUMN,
            BACKFILL_VALUE,
        )

    inspector = _insp()
    ip_type_is_nullable = any(
        column["name"] == IP_TYPE_COLUMN and column.get("nullable", True)
        for column in inspector.get_columns(TABLE, schema=SCHEMA)
    )
    if ip_type_is_nullable:
        op.alter_column(
            TABLE,
            IP_TYPE_COLUMN,
            nullable=False,
            existing_type=sa.String(50),
            existing_nullable=True,
            **_schema_args(),
        )
        logger.info("Set %s.%s NOT NULL", _qualified(TABLE), IP_TYPE_COLUMN)

    _set_primary_key(_insp(), NEW_KEY)


def downgrade():
    bind = op.get_bind()
    inspector = _insp()
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return

    collisions = bind.execute(
        sa.text(
            f"""
            SELECT case_id::text AS case_id, email_id::text AS email_id, ip AS ip,
                   count(*) AS n,
                   string_agg(DISTINCT {IP_TYPE_COLUMN}, ', ' ORDER BY {IP_TYPE_COLUMN}) AS roles
            FROM {_qualified(TABLE)}
            GROUP BY case_id, email_id, ip
            HAVING count(*) > 1
            ORDER BY case_id, email_id, ip
            """
        )
    ).fetchall()

    if collisions:
        listed = "; ".join(
            f"case {row.case_id} email {row.email_id} ip {row.ip} roles {row.roles}"
            for row in collisions
        )
        raise RuntimeError(
            f"Cannot downgrade {TABLE} to key (case_id, email_id, ip): "
            f"{len(collisions)} email/IP pair(s) are recorded under more than one "
            f"role, so the narrower key cannot be recreated without deleting rows. "
            f"Affected: {listed}. Merge or delete those rows explicitly, then retry."
        )

    _set_primary_key(inspector, OLD_KEY)

    op.alter_column(
        TABLE,
        IP_TYPE_COLUMN,
        nullable=True,
        existing_type=sa.String(50),
        existing_nullable=False,
        **_schema_args(),
    )
    logger.info(
        "Restored %s as nullable; the key is narrow again, so an empty role "
        "is once more representable",
        _qualified(TABLE),
    )
