"""Add vm_requests table for VM application workflow

Revision ID: a3b7c9d1e2f4
Revises: 1ae4a06403df
Create Date: 2026-02-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a3b7c9d1e2f4'
down_revision = '1ae4a06403df'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vm_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('resource_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('hostname', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('cores', sa.Integer(), nullable=False),
        sa.Column('memory', sa.Integer(), nullable=False),
        sa.Column('password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('storage', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('environment_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('os_info', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('ostemplate', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('rootfs_size', sa.Integer(), nullable=True),
        sa.Column('unprivileged', sa.Boolean(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('disk_size', sa.Integer(), nullable=True),
        sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('pending', 'approved', 'rejected', name='vmrequeststatus'),
            nullable=False,
        ),
        sa.Column('reviewer_id', sa.Uuid(), nullable=True),
        sa.Column('review_comment', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('vmid', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('vm_requests')
    # Drop the enum type
    sa.Enum('pending', 'approved', 'rejected', name='vmrequeststatus').drop(
        op.get_bind(), checkfirst=True
    )
