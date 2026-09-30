from alembic import op
import sqlalchemy as sa


revision = "20260928_04"
down_revision = "20260928_03"
branch_labels = None
depends_on = None

SCHEMA = None

LAYER_NAME_PREFIX = "Email "


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("emails", schema=SCHEMA):
        return

    resolve_layer = f"""
        WITH email_layer AS (
            SELECT DISTINCT ON (e.case_id, e.email_id)
                   e.case_id,
                   e.email_id,
                   l.id AS layer_id
            FROM emails AS e
            JOIN layers AS l
              ON l.case_id = e.case_id
             AND l.name = '{{prefix}}' || e.email_id::text
            WHERE {{columns}}
            ORDER BY e.case_id, e.email_id, l.id
        )
    """

    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE emails AS e
            SET layer_id = el.layer_id
            FROM email_layer AS el
            WHERE e.case_id = el.case_id
              AND e.email_id = el.email_id
              AND e.layer_id IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE email_targets AS t
            SET layer_id = el.layer_id
            FROM email_layer AS el
            WHERE t.case_id = el.case_id
              AND t.email_id = el.email_id
              AND t.layer_id IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            {resolve_layer.format(prefix=LAYER_NAME_PREFIX, columns="TRUE")}
            UPDATE email_dumps AS d
            SET layer_id = el.layer_id
            FROM email_targets AS t
            JOIN email_layer AS el
              ON el.case_id = t.case_id
             AND el.email_id = t.email_id
            WHERE t.case_id = d.case_id
              AND t.target_id = d.target_id
              AND d.layer_id IS NULL
            """
        )
    )


def downgrade() -> None:
    for table in ("emails", "email_targets", "email_dumps"):
        op.execute(sa.text(f"UPDATE {table} SET layer_id = NULL WHERE layer_id IS NOT NULL"))
