"""compatibility placeholder for cleanup rels

Revision ID: ee01_cleanup_rels
Revises: eb01_add_expiry_warning_hours
Create Date: 2026-05-18 00:00:00.000000

This revision exists because some development databases were stamped with
``ee01_cleanup_rels`` while the matching migration file was not present in the
repository.  Keep it as a no-op bridge so Alembic can resolve those databases
and continue to newer revisions.

"""

revision = "ee01_cleanup_rels"
down_revision = "eb01_add_expiry_warning_hours"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
