from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")

revision = "20260928_08"
down_revision = "20260928_07"
branch_labels = None
depends_on = None

SCHEMA = None

TABLE = "email_dumps"
PK_NAME = "pk_email_dumps"
REDUNDANT_INDEX = "ix_email_dumps_case_id"


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _insp():
    return sa.inspect(op.get_bind())


def _set_primary_key(inspector, columns):
    existing = inspector.get_pk_constraint(TABLE, schema=SCHEMA)
    if existing and existing.get("name"):
        op.drop_constraint(existing["name"], TABLE, type_="primary", **_schema_args())
    op.create_primary_key(PK_NAME, TABLE, columns, **_schema_args())


def upgrade():
    inspector = _insp()
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return

    _set_primary_key(inspector, ["case_id", "target_id", "dump_id"])

    if REDUNDANT_INDEX in {
        index["name"] for index in inspector.get_indexes(TABLE, schema=SCHEMA)
    }:
        op.drop_index(REDUNDANT_INDEX, TABLE, **_schema_args())
        logger.info(
            "Dropped %s, an exact prefix of the new primary key", REDUNDANT_INDEX
        )


def downgrade():
    bind = op.get_bind()
    inspector = _insp()
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return

    collisions = bind.execute(
        sa.text(
            """
            SELECT case_id::text AS case_id, dump_id AS dump_id, count(*) AS n,
                   string_agg(DISTINCT target_id, ', ' ORDER BY target_id) AS targets
            FROM email_dumps
            GROUP BY case_id, dump_id
            HAVING count(*) > 1
            ORDER BY case_id, dump_id
            """
        )
    ).fetchall()

    if collisions:
        listed = "; ".join(
            f"case {row.case_id} dump {row.dump_id} targets {row.targets}"
            for row in collisions
        )
        raise RuntimeError(
            f"Cannot downgrade {TABLE} to key (case_id, dump_id): {len(collisions)} "
            f"dump(s) are recorded against more than one target, so the narrower "
            f"key cannot be recreated without deleting rows. Affected: {listed}. "
            "Re-attribute or delete those rows explicitly, then retry."
        )

    _set_primary_key(inspector, ["case_id", "dump_id"])

    op.create_index(REDUNDANT_INDEX, TABLE, ["case_id"], **_schema_args())
    logger.info("Restored %s alongside the narrower primary key", REDUNDANT_INDEX)
