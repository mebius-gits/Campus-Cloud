"""add teacher judge rubric files

Revision ID: tjfl01_teacher_judge_files
Revises: tjse01_script_executor
Create Date: 2026-06-01 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "tjfl01_teacher_judge_files"
down_revision = "tjse01_script_executor"
branch_labels = None
depends_on = None


file_status_enum = postgresql.ENUM(
    "active",
    "replaced",
    name="teacherjudgefilestatus",
    create_type=False,
)


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    file_status_enum.create(bind, checkfirst=True)

    if not _table_exists("teacher_judge_files"):
        op.create_table(
            "teacher_judge_files",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("group_id", sa.Uuid(), nullable=False),
            sa.Column("uploaded_by", sa.Uuid(), nullable=True),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("file_hash", sa.String(length=64), nullable=False),
            sa.Column("template_key", sa.String(length=50), nullable=False),
            sa.Column(
                "analysis_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "status",
                file_status_enum,
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["group_id"], ["group.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["uploaded_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_group_id"),
        "teacher_judge_files",
        ["group_id"],
    )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_uploaded_by"),
        "teacher_judge_files",
        ["uploaded_by"],
    )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_file_hash"),
        "teacher_judge_files",
        ["file_hash"],
    )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_template_key"),
        "teacher_judge_files",
        ["template_key"],
    )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_status"),
        "teacher_judge_files",
        ["status"],
    )
    _create_index_if_missing(
        op.f("ix_teacher_judge_files_created_at"),
        "teacher_judge_files",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_teacher_judge_files_group_filename",
        "teacher_judge_files",
        ["group_id", "original_filename"],
    )
    _create_index_if_missing(
        "ix_teacher_judge_files_group_created",
        "teacher_judge_files",
        ["group_id", "created_at"],
    )
    if not _index_exists(
        "teacher_judge_files",
        "uq_teacher_judge_files_active_filename",
    ):
        op.create_index(
            "uq_teacher_judge_files_active_filename",
            "teacher_judge_files",
            ["group_id", "original_filename"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )

    if _table_exists("teacher_judge_script_artifacts"):
        if not _column_exists("teacher_judge_script_artifacts", "source_file_id"):
            op.add_column(
                "teacher_judge_script_artifacts",
                sa.Column("source_file_id", sa.Uuid(), nullable=True),
            )
            op.create_foreign_key(
                "fk_teacher_judge_script_artifacts_source_file_id",
                "teacher_judge_script_artifacts",
                "teacher_judge_files",
                ["source_file_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if not _column_exists(
            "teacher_judge_script_artifacts",
            "source_file_snapshot_json",
        ):
            op.add_column(
                "teacher_judge_script_artifacts",
                sa.Column(
                    "source_file_snapshot_json",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'::json"),
                ),
            )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_source_file_id"),
            "teacher_judge_script_artifacts",
            ["source_file_id"],
        )


def downgrade() -> None:
    if _table_exists("teacher_judge_script_artifacts"):
        if _index_exists(
            "teacher_judge_script_artifacts",
            op.f("ix_teacher_judge_script_artifacts_source_file_id"),
        ):
            op.drop_index(
                op.f("ix_teacher_judge_script_artifacts_source_file_id"),
                table_name="teacher_judge_script_artifacts",
            )
        if _column_exists("teacher_judge_script_artifacts", "source_file_id"):
            op.drop_constraint(
                "fk_teacher_judge_script_artifacts_source_file_id",
                "teacher_judge_script_artifacts",
                type_="foreignkey",
            )
            op.drop_column("teacher_judge_script_artifacts", "source_file_id")
        if _column_exists(
            "teacher_judge_script_artifacts",
            "source_file_snapshot_json",
        ):
            op.drop_column(
                "teacher_judge_script_artifacts",
                "source_file_snapshot_json",
            )

    if _table_exists("teacher_judge_files"):
        for index_name in (
            "ix_teacher_judge_files_group_created",
            "ix_teacher_judge_files_group_filename",
            "uq_teacher_judge_files_active_filename",
            op.f("ix_teacher_judge_files_created_at"),
            op.f("ix_teacher_judge_files_status"),
            op.f("ix_teacher_judge_files_template_key"),
            op.f("ix_teacher_judge_files_file_hash"),
            op.f("ix_teacher_judge_files_uploaded_by"),
            op.f("ix_teacher_judge_files_group_id"),
        ):
            if _index_exists("teacher_judge_files", index_name):
                op.drop_index(index_name, table_name="teacher_judge_files")
        op.drop_table("teacher_judge_files")

    file_status_enum.drop(op.get_bind(), checkfirst=True)
