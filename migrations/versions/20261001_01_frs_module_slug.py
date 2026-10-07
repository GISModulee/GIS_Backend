"""Widen the module_slug CHECK constraints to include the FRS slug.

Root cause
----------
`models/model.py` does not hard-code the whitelist. It builds
`_MODULE_SLUG_ALLOWED_SQL` from `ALLOWED_MODULE_SLUGS` at import time
and attaches the result to `ck_layers_module_slug_allowed` and
`ck_features_module_slug_allowed`. Adding `face-recognition-system` to
that frozenset therefore changes what the *application* expects on the
next import, while the *deployed* constraint still carries the previous
narrower list. The ORM metadata and the database silently disagree.

The visible symptom is every FRS insert failing a check-constraint
violation even though the code accepts the slug: `LayerCreate` validates
`module_slug` against `ALLOWED_MODULE_SLUGS` and passes, `create_layer`
sends the new value, and Postgres rejects it. Re-importing the email
dump or any `gis` row still works, so it looks like a fault in the new
module rather than a schema/ORM drift.

This migration drops and recreates both constraints, generating the SQL
literal from the same `ALLOWED_MODULE_SLUGS` the model reads, so the
database and the application cannot drift apart. The literal is built
here rather than hard-coded for the same reason.

No data is rewritten. Every existing row's `module_slug` is already in
the current whitelist — the constraint being replaced was a subset of
it — so the new constraint accepts all of them. This is a constraint
swap only.

Both constraints are checked with the inspector before being dropped, so
re-running against a database that already has (or has never had) a
given constraint does not fail on a missing object.
"""

from alembic import op
import sqlalchemy as sa

from utils.constants import ALLOWED_MODULE_SLUGS


revision = "20261001_01"
down_revision = "20260928_09"
branch_labels = None
depends_on = None

# Tables are unqualified in the ORM and may live in either the first
# available search-path schema or public. None keeps migration behavior
# aligned with the application's configured search path.
SCHEMA = None

# Same construction as models.model._MODULE_SLUG_ALLOWED_SQL, so the
# recreated constraint matches what the ORM will emit.
_SQL_ALLOWED = ", ".join(
    f"'{slug}'" for slug in sorted(ALLOWED_MODULE_SLUGS)
)


def _recreate(table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    constraint_name = f"ck_{table}_module_slug_allowed"

    existing = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints(table, schema=SCHEMA)
    }
    if constraint_name in existing:
        op.drop_constraint(constraint_name, table, type_="check", schema=SCHEMA)

    op.create_check_constraint(
        constraint_name,
        table,
        f"module_slug IN ({_SQL_ALLOWED})",
        schema=SCHEMA,
    )


def upgrade() -> None:
    _recreate("layers")
    _recreate("features")


def downgrade() -> None:
    """Rebuild both constraints from the current whitelist.

    This is not a true reversal, and it cannot be. The previous narrower
    list is not recoverable from anywhere in this repository: it lived in
    the deployed database's constraint text, not in a constant that
    still exists — `ALLOWED_MODULE_SLUGS` has already been widened, and
    the literal is generated from it. Recreating the constraint to the
    current whitelist is the only state this file can reconstruct.

    The practical effect of running this downgrade is therefore no change
    to the allowed values, not a removal of the FRS slug. Re-adding rows
    carrying `face-recognition-system` is a data question, not a schema
    one, and is left untouched here; nothing about the constraint swap
    affected the rows already stored.
    """
    _recreate("layers")
    _recreate("features")
