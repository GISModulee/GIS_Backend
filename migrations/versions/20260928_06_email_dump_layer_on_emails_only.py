from alembic import op
import sqlalchemy as sa
import logging


logger = logging.getLogger("alembic.email_dump")

revision = "20260928_06"
down_revision = "20260928_05"
branch_labels = None
depends_on = None

SCHEMA = None

TABLES = ("email_dumps", "email_targets")

ALL_TABLES = ("emails", "email_targets", "email_dumps")


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def _drop_layer_id(inspector, table):
    if not _table_exists(inspector, table):
        return

    for fk in inspector.get_foreign_keys(table, schema=SCHEMA):
        if fk["referred_table"] == "layers" and "layer_id" in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey", **_schema_args())

    for index in inspector.get_indexes(table, schema=SCHEMA):
        if index["column_names"] == ["layer_id"]:
            op.drop_index(index["name"], table, **_schema_args())

    columns = {c["name"] for c in inspector.get_columns(table, schema=SCHEMA)}
    if "layer_id" in columns:
        op.drop_column(table, "layer_id", **_schema_args())


def _delete_orphans():
    removed_dumps = op.get_bind().execute(
        sa.text(
            """
            DELETE FROM email_dumps AS d
            WHERE NOT EXISTS (
                SELECT 1
                FROM email_targets AS t
                JOIN emails AS e
                  ON e.case_id = t.case_id AND e.email_id = t.email_id
                JOIN layers AS l ON l.id = e.layer_id
                WHERE t.case_id = d.case_id AND t.target_id = d.target_id
            )
            """
        )
    ).rowcount

    removed_targets = op.get_bind().execute(
        sa.text(
            """
            DELETE FROM email_targets AS t
            WHERE NOT EXISTS (
                SELECT 1
                FROM emails AS e
                JOIN layers AS l ON l.id = e.layer_id
                WHERE e.case_id = t.case_id AND e.email_id = t.email_id
            )
            """
        )
    ).rowcount

    if removed_dumps or removed_targets:
        logger.info(
            "Removed %s target(s) and %s dump(s) with no email left on a layer",
            removed_targets,
            removed_dumps,
        )


def _relax_email_id(inspector):
    if not _table_exists(inspector, "email_targets"):
        return

    columns = {c["name"]: c for c in inspector.get_columns("email_targets", schema=SCHEMA)}
    column = columns.get("email_id")
    if column is None or column["nullable"]:
        return

    op.alter_column(
        "email_targets",
        "email_id",
        existing_type=sa.String(length=100),
        nullable=True,
        **_schema_args(),
    )


def _tighten_email_id():
    bind = op.get_bind()
    removed_dumps = bind.execute(
        sa.text(
            """
            DELETE FROM email_dumps AS d
            WHERE EXISTS (
                SELECT 1 FROM email_targets AS t
                WHERE t.case_id = d.case_id
                  AND t.target_id = d.target_id
                  AND t.email_id IS NULL
            )
            """
        )
    ).rowcount
    removed_targets = bind.execute(
        sa.text("DELETE FROM email_targets WHERE email_id IS NULL")
    ).rowcount

    if removed_dumps or removed_targets:
        logger.info(
            "Removed %s dropdown-only target(s) and %s dump(s) that name no email",
            removed_targets,
            removed_dumps,
        )

    op.alter_column(
        "email_targets",
        "email_id",
        existing_type=sa.String(length=100),
        nullable=False,
        **_schema_args(),
    )


def _backfill_layer_id():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE email_targets AS t
            SET layer_id = src.layer_id
            FROM (
                SELECT e.case_id, e.email_id, min(e.layer_id) AS layer_id
                FROM emails AS e
                GROUP BY e.case_id, e.email_id
            ) AS src
            WHERE src.case_id = t.case_id AND src.email_id = t.email_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE email_dumps AS d
            SET layer_id = src.layer_id
            FROM (
                SELECT t.case_id, t.target_id, min(e.layer_id) AS layer_id
                FROM email_targets AS t
                JOIN emails AS e
                  ON e.case_id = t.case_id AND e.email_id = t.email_id
                GROUP BY t.case_id, t.target_id
            ) AS src
            WHERE src.case_id = d.case_id AND src.target_id = d.target_id
            """
        )
    )


def _delete_unlayered():
    bind = op.get_bind()
    for table in TABLES:
        removed = bind.execute(
            sa.text(
                f"""
                DELETE FROM {table} AS t
                WHERE t.layer_id IS NULL
                   OR NOT EXISTS (
                       SELECT 1 FROM layers AS l WHERE l.id = t.layer_id
                   )
                """
            )
        ).rowcount
        if removed:
            logger.info("Removed %s %s row(s) with no layer to restore", removed, table)


def upgrade() -> None:
    inspector = _insp()
    if not _table_exists(inspector, "emails"):
        return

    _delete_orphans()
    _relax_email_id(_insp())

    for table in TABLES:
        _drop_layer_id(_insp(), table)


def downgrade() -> None:
    inspector = _insp()
    if not _table_exists(inspector, "emails"):
        return

    for table in TABLES:
        if "layer_id" in {c["name"] for c in _insp().get_columns(table, schema=SCHEMA)}:
            continue
        op.add_column(
            table,
            sa.Column("layer_id", sa.Integer(), nullable=True, **_schema_args()),
        )
        op.create_index(f"ix_{table}_layer_id", table, ["layer_id"], **_schema_args())
        op.create_foreign_key(
            f"fk_{table}_layer",
            table,
            "layers",
            ["layer_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )

    _backfill_layer_id()
    _delete_unlayered()

    for table in TABLES:
        op.alter_column(
            table,
            "layer_id",
            existing_type=sa.Integer(),
            nullable=False,
            **_schema_args(),
        )

    _tighten_email_id()
