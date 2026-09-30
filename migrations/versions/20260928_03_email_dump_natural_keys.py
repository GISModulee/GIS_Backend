from alembic import op
import sqlalchemy as sa


revision = "20260928_03"
down_revision = "20260928_02"
branch_labels = None
depends_on = None

SCHEMA = None

TABLES = ("emails", "email_targets", "email_dumps")

NEW_PKS = {
    "emails": ("case_id", "email_id", "ip"),
    "email_targets": ("case_id", "target_id"),
    "email_dumps": ("case_id", "dump_id"),
}

OLD_UNIQUES = {
    "emails": "uq_emails_case_email_ip",
    "email_targets": "uq_email_targets_email_target",
    "email_dumps": "uq_email_dumps_target_dump",
}

OLD_UNIQUE_COLUMNS = {
    "emails": ["case_id", "email_id", "ip"],
    "email_targets": ["email_id", "target_id"],
    "email_dumps": ["target_id", "dump_id"],
}

OLD_PKS = {
    "emails": "emails_pkey",
    "email_targets": "email_targets_pkey",
    "email_dumps": "email_dumps_pkey",
}


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(inspector, name):
    return inspector.has_table(name, schema=SCHEMA)


def _columns(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {c["name"] for c in inspector.get_columns(table, schema=SCHEMA)}


def _fk_names(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {f["name"] for f in inspector.get_foreign_keys(table, schema=SCHEMA)}


def _fks_to(inspector, table, referred_table):
    if not _table_exists(inspector, table):
        return []
    return [
        f
        for f in inspector.get_foreign_keys(table, schema=SCHEMA)
        if f["referred_table"] == referred_table
    ]


def _index_names(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {i["name"] for i in inspector.get_indexes(table, schema=SCHEMA)}


def _unique_names(inspector, table):
    if not _table_exists(inspector, table):
        return set()
    return {u["name"] for u in inspector.get_unique_constraints(table, schema=SCHEMA)}


def _schema_args():
    return {"schema": SCHEMA} if SCHEMA else {}


def _add_layer_id(inspector, table):
    if not _table_exists(inspector, table):
        return

    if "layer_id" not in _columns(inspector, table):
        op.add_column(
            table,
            sa.Column("layer_id", sa.Integer(), nullable=True, **_schema_args()),
        )

    if f"ix_{table}_layer_id" not in _index_names(inspector, table):
        op.create_index(f"ix_{table}_layer_id", table, ["layer_id"], **_schema_args())

    if not _fks_to(inspector, table, "layers"):
        op.create_foreign_key(
            f"fk_{table}_layer",
            table,
            "layers",
            ["layer_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )


def _rewrite_surrogates(inspector, bind):
    _drop_incoming_foreign_keys(inspector)

    if _table_exists(inspector, "email_targets") and "id" in _columns(inspector, "email_targets"):
        op.execute(
            sa.text(
                """
                UPDATE email_targets AS t
                SET email_id = e.email_id
                FROM emails AS e
                WHERE t.email_id = e.id
                """
            )
        )

    if _table_exists(inspector, "email_dumps") and "id" in _columns(inspector, "email_dumps"):
        op.alter_column(
            "email_dumps",
            "target_id",
            type_=sa.String(100),
            existing_type=sa.Integer(),
            **_schema_args(),
        )
        op.execute(
            sa.text(
                """
                UPDATE email_dumps AS d
                SET target_id = t.target_id
                FROM email_targets AS t
                WHERE d.target_id::text = t.id::text
                """
            )
        )


def _drop_incoming_foreign_keys(inspector):
    for table in ("email_targets", "email_dumps"):
        for name in sorted(_fk_names(inspector, table)):
            op.drop_constraint(name, table, type_="foreignkey", **_schema_args())


def _drop_old_uniques_and_pks(inspector):
    for table in TABLES:
        uniques = _unique_names(inspector, table)
        old = OLD_UNIQUES.get(table)
        if old and old in uniques:
            op.drop_constraint(old, table, type_="unique", **_schema_args())

    for table in TABLES:
        if "id" not in _columns(inspector, table):
            continue
        name = OLD_PKS.get(table)
        if name:
            op.drop_constraint(name, table, type_="primary", **_schema_args())


def _create_new_pks(inspector):
    for table, pk_columns in NEW_PKS.items():
        if not _table_exists(inspector, table):
            continue
        current = inspector.get_pk_constraint(table, schema=SCHEMA)[
            "constrained_columns"
        ]
        if current == list(pk_columns):
            continue
        op.create_primary_key(f"pk_{table}", table, list(pk_columns), **_schema_args())


def _drop_surrogate_columns(inspector):
    for table in TABLES:
        if "id" not in _columns(inspector, table):
            continue
        op.drop_column(table, "id", **_schema_args())


def _tighten_child_columns(inspector):
    op.execute(
        sa.text(
            "DELETE FROM email_dumps WHERE case_id IS NULL "
            "OR dump_id IS NULL OR target_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM email_targets WHERE case_id IS NULL OR target_id IS NULL"
        )
    )
    op.execute(
        sa.text("DELETE FROM emails WHERE case_id IS NULL OR email_id IS NULL OR ip IS NULL")
    )

    key_types = {
        "ip": sa.String(45),
        "dump_id": sa.String(100),
        "target_id": sa.String(100),
    }

    for table, pk_columns in NEW_PKS.items():
        for column in pk_columns:
            op.alter_column(
                table,
                column,
                nullable=False,
                existing_type=key_types.get(column, sa.Integer()),
                **_schema_args(),
            )

    if not _fks_to(inspector, "email_dumps", "email_targets"):
        op.create_foreign_key(
            "fk_email_dumps_target",
            "email_dumps",
            "email_targets",
            ["case_id", "target_id"],
            ["case_id", "target_id"],
            ondelete="CASCADE",
            **_schema_args(),
        )


def upgrade() -> None:
    if not _table_exists(_insp(), "emails"):
        return

    _rewrite_surrogates(_insp(), op.get_bind())
    _drop_old_uniques_and_pks(_insp())

    for table in TABLES:
        _add_layer_id(_insp(), table)

    _create_new_pks(_insp())
    _tighten_child_columns(_insp())
    _drop_surrogate_columns(_insp())


def downgrade() -> None:
    if not _table_exists(_insp(), "emails"):
        return

    for name in sorted(_fk_names(_insp(), "email_dumps")):
        op.drop_constraint(name, "email_dumps", type_="foreignkey", **_schema_args())

    for table in TABLES:
        existing_pk = _insp().get_pk_constraint(table, schema=SCHEMA)["name"]
        if existing_pk:
            op.drop_constraint(existing_pk, table, type_="primary", **_schema_args())

    for table in TABLES:
        inspector = _insp()
        if "id" not in _columns(inspector, table):
            op.add_column(
                table, sa.Column("id", sa.Integer(), nullable=True, **_schema_args())
            )
            op.create_index(f"ix_{table}_id", table, ["id"], **_schema_args())

    for table, pk_columns in NEW_PKS.items():
        join_condition = " AND ".join(f"t.{c} = n.{c}" for c in pk_columns)
        op.execute(
            sa.text(
                f"""
                UPDATE {table} AS t
                SET id = n.n
                FROM (
                    SELECT row_number() OVER (ORDER BY {", ".join(pk_columns)}) AS n,
                           {", ".join(pk_columns)}
                    FROM {table}
                ) AS n
                WHERE {join_condition}
                """
            )
        )
        op.alter_column(
            table,
            "id",
            nullable=False,
            existing_type=sa.Integer(),
            **_schema_args(),
        )
        op.create_primary_key(OLD_PKS[table], table, ["id"], **_schema_args())

    op.execute(
        sa.text(
            """
            UPDATE email_targets AS t
            SET email_id = e.id
            FROM emails AS e
            WHERE e.case_id = t.case_id AND e.email_id = t.email_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE email_dumps AS d
            SET target_id = t.id
            FROM email_targets AS t
            WHERE t.case_id = d.case_id AND t.target_id = d.target_id
            """
        )
    )

    op.execute(sa.text("ALTER TABLE email_dumps ALTER COLUMN target_id TYPE INTEGER USING target_id::integer"))

    if not _fks_to(_insp(), "email_targets", "emails"):
        op.create_foreign_key(
            "fk_email_targets_email",
            "email_targets",
            "emails",
            ["email_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )
    if not _fks_to(_insp(), "email_dumps", "email_targets"):
        op.create_foreign_key(
            "fk_email_dumps_target",
            "email_dumps",
            "email_targets",
            ["target_id"],
            ["id"],
            ondelete="CASCADE",
            **_schema_args(),
        )

    for table in TABLES:
        inspector = _insp()
        if "layer_id" in _columns(inspector, table) and not _fks_to(
            inspector, table, "layers"
        ):
            op.create_foreign_key(
                f"fk_{table}_layer",
                table,
                "layers",
                ["layer_id"],
                ["id"],
                ondelete="CASCADE",
                **_schema_args(),
            )

    for table in TABLES:
        if OLD_UNIQUES[table] in _unique_names(_insp(), table):
            continue
        op.create_unique_constraint(
            OLD_UNIQUES[table], table, OLD_UNIQUE_COLUMNS[table], **_schema_args()
        )
