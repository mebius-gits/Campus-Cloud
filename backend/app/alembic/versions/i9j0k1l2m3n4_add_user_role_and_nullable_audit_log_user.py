"""add user role and nullable audit log user

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


user_role_enum = sa.Enum("student", "teacher", "admin", name="userrole")


def upgrade() -> None:
    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "user",
        sa.Column("role", user_role_enum, nullable=False, server_default="student"),
    )
    op.execute(
        """
        UPDATE "user"
        SET role = (
            CASE
                WHEN is_superuser THEN 'admin'
                WHEN is_instructor THEN 'teacher'
                ELSE 'student'
            END
        )::userrole
        """
    )
    op.alter_column("user", "role", server_default=None)

    op.drop_constraint(
        op.f("audit_logs_user_id_fkey"), "audit_logs", type_="foreignkey"
    )
    op.alter_column(
        "audit_logs",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_foreign_key(
        op.f("audit_logs_user_id_fkey"),
        "audit_logs",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("audit_logs_user_id_fkey"), "audit_logs", type_="foreignkey"
    )
    op.execute(
        """
        DELETE FROM audit_logs
        WHERE user_id IS NULL
        """
    )
    op.alter_column(
        "audit_logs",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        op.f("audit_logs_user_id_fkey"),
        "audit_logs",
        "user",
        ["user_id"],
        ["id"],
    )

    op.drop_column("user", "role")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
