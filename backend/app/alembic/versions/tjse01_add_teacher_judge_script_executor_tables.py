"""add teacher judge script executor tables

Revision ID: tjse01_script_executor
Revises: tjtc01_template_commands
Create Date: 2026-05-30 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "tjse01_script_executor"
down_revision = "tjtc01_template_commands"
branch_labels = None
depends_on = None


script_language_enum = postgresql.ENUM(
    "python",
    "shell",
    "bat",
    name="teacherjudgescriptlanguage",
    create_type=False,
)
script_source_enum = postgresql.ENUM(
    "ai_generated",
    "regenerated",
    name="teacherjudgescriptsource",
    create_type=False,
)
script_status_enum = postgresql.ENUM(
    "draft",
    "review_failed",
    "reviewed",
    "approved",
    "archived",
    name="teacherjudgescriptstatus",
    create_type=False,
)
run_target_scope_enum = postgresql.ENUM(
    "all_with_vm",
    "running_only",
    "manual",
    name="teacherjudgescriptruntargetscope",
    create_type=False,
)
run_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="teacherjudgescriptrunstatus",
    create_type=False,
)


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        index["name"] == index_name for index in inspector.get_indexes(table_name)
    )


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    script_language_enum.create(bind, checkfirst=True)
    script_source_enum.create(bind, checkfirst=True)
    script_status_enum.create(bind, checkfirst=True)
    run_target_scope_enum.create(bind, checkfirst=True)
    run_status_enum.create(bind, checkfirst=True)

    if not _table_exists("teacher_judge_script_artifacts"):
        op.create_table(
            "teacher_judge_script_artifacts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("group_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("template_key", sa.String(length=50), nullable=False),
            sa.Column("rubric_snapshot_json", sa.JSON(), nullable=False),
            sa.Column(
                "script_language",
                script_language_enum,
                nullable=False,
                server_default="python",
            ),
            sa.Column("script_content", sa.Text(), nullable=False),
            sa.Column(
                "source",
                script_source_enum,
                nullable=False,
                server_default="ai_generated",
            ),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "status",
                script_status_enum,
                nullable=False,
                server_default="draft",
            ),
            sa.Column(
                "policy_check_result_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "ai_review_result_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("approved_by", sa.Uuid(), nullable=True),
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
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["approved_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["group_id"], ["group.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.alter_column(
            "teacher_judge_script_artifacts",
            "script_language",
            server_default=None,
        )
        op.alter_column("teacher_judge_script_artifacts", "source", server_default=None)
        op.alter_column(
            "teacher_judge_script_artifacts",
            "version",
            server_default=None,
        )
        op.alter_column("teacher_judge_script_artifacts", "status", server_default=None)
        op.alter_column(
            "teacher_judge_script_artifacts",
            "policy_check_result_json",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_artifacts",
            "ai_review_result_json",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_artifacts",
            "created_at",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_artifacts",
            "updated_at",
            server_default=None,
        )

    if not _table_exists("teacher_judge_script_runs"):
        op.create_table(
            "teacher_judge_script_runs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("group_id", sa.Uuid(), nullable=False),
            sa.Column("artifact_id", sa.Uuid(), nullable=False),
            sa.Column(
                "target_scope",
                run_target_scope_enum,
                nullable=False,
                server_default="all_with_vm",
            ),
            sa.Column(
                "target_snapshot_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "status",
                run_status_enum,
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "progress_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "result_summary_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column(
                "target_results_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
            sa.Column("started_by", sa.Uuid(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["artifact_id"],
                ["teacher_judge_script_artifacts.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["group_id"], ["group.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["started_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.alter_column(
            "teacher_judge_script_runs",
            "target_scope",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_runs",
            "target_snapshot_json",
            server_default=None,
        )
        op.alter_column("teacher_judge_script_runs", "status", server_default=None)
        op.alter_column(
            "teacher_judge_script_runs",
            "progress_json",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_runs",
            "result_summary_json",
            server_default=None,
        )
        op.alter_column(
            "teacher_judge_script_runs",
            "target_results_json",
            server_default=None,
        )
        op.alter_column("teacher_judge_script_runs", "created_at", server_default=None)
        op.alter_column("teacher_judge_script_runs", "updated_at", server_default=None)

    if _table_exists("teacher_judge_script_artifacts"):
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_group_id"),
            "teacher_judge_script_artifacts",
            ["group_id"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_template_key"),
            "teacher_judge_script_artifacts",
            ["template_key"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_status"),
            "teacher_judge_script_artifacts",
            ["status"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_created_by"),
            "teacher_judge_script_artifacts",
            ["created_by"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_artifacts_created_at"),
            "teacher_judge_script_artifacts",
            ["created_at"],
        )
        _create_index_if_missing(
            "ix_teacher_judge_script_artifacts_group_status",
            "teacher_judge_script_artifacts",
            ["group_id", "status"],
        )
        _create_index_if_missing(
            "ix_teacher_judge_script_artifacts_group_created",
            "teacher_judge_script_artifacts",
            ["group_id", "created_at"],
        )

    if _table_exists("teacher_judge_script_runs"):
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_runs_group_id"),
            "teacher_judge_script_runs",
            ["group_id"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_runs_artifact_id"),
            "teacher_judge_script_runs",
            ["artifact_id"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_runs_status"),
            "teacher_judge_script_runs",
            ["status"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_runs_started_by"),
            "teacher_judge_script_runs",
            ["started_by"],
        )
        _create_index_if_missing(
            op.f("ix_teacher_judge_script_runs_created_at"),
            "teacher_judge_script_runs",
            ["created_at"],
        )
        _create_index_if_missing(
            "ix_teacher_judge_script_runs_group_status",
            "teacher_judge_script_runs",
            ["group_id", "status"],
        )
        _create_index_if_missing(
            "ix_teacher_judge_script_runs_artifact_created",
            "teacher_judge_script_runs",
            ["artifact_id", "created_at"],
        )


def downgrade() -> None:
    # Intentionally no-op: this migration is used to safely create production data
    # tables and must not drop existing Teacher Judge artifacts or run records.
    pass
