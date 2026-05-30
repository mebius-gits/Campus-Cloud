"""Teacher Judge managed script artifact lifecycle service."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, desc, func, select

from app.ai.teacher_judge.config import settings
from app.ai.teacher_judge.schemas import (
    RubricAnalysis,
    TeacherJudgeScriptArtifactPublic,
)
from app.ai.teacher_judge.script_policy import check_script_policy
from app.ai.teacher_judge.service import _call_vllm
from app.ai.teacher_judge.template_command_service import get_enabled_template_commands
from app.ai.utils import apply_thinking_control
from app.models.teacher_judge_script_artifact import (
    TeacherJudgeScriptArtifact,
    TeacherJudgeScriptLanguage,
    TeacherJudgeScriptSource,
    TeacherJudgeScriptStatus,
)
from app.models.teacher_judge_template_command import TeacherJudgeTemplateCommand

logger = logging.getLogger(__name__)


SCRIPT_GENERATION_SYSTEM_PROMPT = """
# 角色
你是 Teacher Judge 的受管 Python 檢測腳本產生器。

# 任務
根據 rubric snapshot 產生一份只讀、可重複執行的 Python managed script。

# 硬性規則
- 只能輸出 JSON，不要 markdown。
- JSON 欄位必須是 {"script_content": "..."}。
- script_content 必須是完整 Python 程式。
- 腳本只能讀取本機服務狀態、port、process、HTTP localhost endpoint。
- 腳本不得刪除、修改、修復、安裝、重啟、停用或重設任何環境。
- 腳本不得讀取 .env、.ssh、private key 或把資料送到外部網路。
- 若需要執行指令，只能使用 subprocess.run([...], timeout=秒數, capture_output=True, text=True, check=False)。
- subprocess.run 第一個參數必須是 argv list，不得使用字串指令，不得使用 shell=True。
- 不得使用 os.system、os.popen、subprocess.Popen 或任何未設定 timeout 的指令執行方式。
- 若 template command 含 pipe、redirect、grep 等 shell 寫法，請改用 Python 程式解析 stdout，不要原樣 shell=True 執行。
- HTTP request 只允許 GET/HEAD localhost/127.0.0.1/::1，必須設定 timeout。
- 腳本最後必須 print 單一 JSON，schema_version 固定為 teacher_judge_result.v1。
- 優先根據 rubric item 的 check_steps.command_key 對應 template_commands 產生檢查。
- 若 previous_review_feedback 有內容，代表上一輪腳本審查未通過；必須修正其中所有 policy/AI reviewer 問題。

# managed script 輸出 JSON contract
{
  "schema_version": "teacher_judge_result.v1",
  "summary": "檢查摘要",
  "checks": [
    {
      "id": "stable_check_id",
      "title": "檢查名稱",
      "status": "pass | fail | warning | unknown | skipped",
      "evidence": "可讀證據",
      "raw": "必要時放原始片段"
    }
  ],
  "errors": []
}
""".strip()


AI_REVIEWER_SYSTEM_PROMPT = """
你是 Teacher Judge managed script 的安全審查員。
只審查腳本，不執行腳本。請依 policy 判斷它是否只做 read-only inspection。
只輸出 JSON：
{
  "approved": true,
  "risk_level": "low | medium | high",
  "issues": [],
  "suggested_fix": null
}
若腳本可能刪除、修改、修復、安裝、重啟、讀取敏感檔案或對外傳資料，approved 必須是 false。
""".strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ai_review(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "approved": False,
            "risk_level": "high",
            "issues": ["AI reviewer 回傳格式不正確"],
            "suggested_fix": "請重新生成腳本",
        }

    approved = payload.get("approved") is True
    risk_level = str(payload.get("risk_level") or ("low" if approved else "high"))
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "high"

    issues = payload.get("issues")
    if not isinstance(issues, list):
        issues = []

    return {
        "approved": approved,
        "risk_level": risk_level,
        "issues": [str(issue) for issue in issues],
        "suggested_fix": payload.get("suggested_fix"),
    }


def _artifact_to_public(
    artifact: TeacherJudgeScriptArtifact,
) -> TeacherJudgeScriptArtifactPublic:
    return TeacherJudgeScriptArtifactPublic(
        id=str(artifact.id),
        group_id=str(artifact.group_id),
        name=artifact.name,
        template_key=artifact.template_key,
        rubric_snapshot_json=artifact.rubric_snapshot_json,
        script_language=artifact.script_language.value,
        script_content=artifact.script_content,
        source=artifact.source.value,
        version=artifact.version,
        status=artifact.status.value,
        policy_check_result_json=artifact.policy_check_result_json,
        ai_review_result_json=artifact.ai_review_result_json,
        created_by=str(artifact.created_by) if artifact.created_by else None,
        approved_by=str(artifact.approved_by) if artifact.approved_by else None,
        created_at=artifact.created_at.isoformat(),
        updated_at=artifact.updated_at.isoformat(),
        approved_at=artifact.approved_at.isoformat() if artifact.approved_at else None,
    )


def _rubric_snapshot(analysis: RubricAnalysis, template_key: str) -> dict[str, Any]:
    snapshot = analysis.model_dump(mode="json")
    snapshot["template_key"] = template_key
    return snapshot


def _template_commands_snapshot(
    commands: list[TeacherJudgeTemplateCommand] | None,
) -> list[dict[str, Any]]:
    if not commands:
        return []

    return [
        {
            "command_key": command.command_key,
            "command_label": command.command_label,
            "category": command.category,
            "command_template": command.command_template,
            "description": command.description,
            "risk_level": command.risk_level,
            "requires_confirmation": command.requires_confirmation,
        }
        for command in commands
    ]


def _with_template_command_catalog(
    rubric_snapshot: dict[str, Any],
    template_commands: list[TeacherJudgeTemplateCommand] | None,
) -> dict[str, Any]:
    snapshot = dict(rubric_snapshot)
    command_catalog = _template_commands_snapshot(template_commands)
    if command_catalog:
        snapshot["template_commands"] = command_catalog
    return snapshot


def _previous_review_feedback(
    artifact: TeacherJudgeScriptArtifact,
) -> dict[str, Any] | None:
    policy_check = artifact.policy_check_result_json or {}
    ai_review = artifact.ai_review_result_json or {}
    policy_issues = policy_check.get("issues")
    ai_issues = ai_review.get("issues")
    feedback = {
        "policy_approved": policy_check.get("approved"),
        "policy_issues": policy_issues if isinstance(policy_issues, list) else [],
        "ai_review_approved": ai_review.get("approved"),
        "ai_review_issues": ai_issues if isinstance(ai_issues, list) else [],
        "ai_review_suggested_fix": ai_review.get("suggested_fix"),
    }
    has_failed_review = (
        feedback["policy_approved"] is False
        or feedback["ai_review_approved"] is False
        or bool(feedback["policy_issues"])
        or bool(feedback["ai_review_issues"])
        or bool(feedback["ai_review_suggested_fix"])
    )
    if not has_failed_review:
        return None
    return feedback


def _resolve_status(
    policy_check: dict[str, Any],
    ai_review: dict[str, Any],
) -> TeacherJudgeScriptStatus:
    if policy_check.get("approved") is True and ai_review.get("approved") is True:
        return TeacherJudgeScriptStatus.reviewed
    return TeacherJudgeScriptStatus.review_failed


async def generate_script_content(
    *,
    rubric_snapshot: dict[str, Any],
    template_key: str,
) -> str:
    if not settings.VLLM_MODEL_NAME:
        raise HTTPException(status_code=503, detail="VLLM_MODEL_NAME 未設定。")

    payload = apply_thinking_control(
        {
            "model": settings.VLLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": SCRIPT_GENERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "template_key": template_key,
                            "rubric_snapshot": rubric_snapshot,
                            "template_commands": rubric_snapshot.get(
                                "template_commands", []
                            ),
                            "previous_review_feedback": rubric_snapshot.get(
                                "previous_review_feedback"
                            ),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": settings.VLLM_CHAT_MAX_TOKENS,
            "temperature": 0.1,
            "top_p": settings.VLLM_TOP_P,
            "response_format": {"type": "json_object"},
        },
        settings.VLLM_ENABLE_THINKING,
    )
    content, _metrics = await _call_vllm(payload, timeout=float(settings.VLLM_TIMEOUT))

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI 產生腳本格式不是 JSON。") from exc

    script_content = str(parsed.get("script_content") or "").strip()
    if not script_content:
        raise HTTPException(status_code=502, detail="AI 未產生 script_content。")
    return script_content


async def review_script_with_ai(
    *,
    script_content: str,
    rubric_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if not settings.VLLM_MODEL_NAME:
        raise HTTPException(status_code=503, detail="VLLM_MODEL_NAME 未設定。")

    payload = apply_thinking_control(
        {
            "model": settings.VLLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": AI_REVIEWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "script_content": script_content,
                            "rubric_snapshot": rubric_snapshot,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": min(settings.VLLM_CHAT_MAX_TOKENS, 2048),
            "temperature": 0.0,
            "top_p": settings.VLLM_TOP_P,
            "response_format": {"type": "json_object"},
        },
        settings.VLLM_ENABLE_THINKING,
    )
    content, _metrics = await _call_vllm(payload, timeout=float(settings.VLLM_TIMEOUT))

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {}
    return _normalize_ai_review(parsed)


async def build_reviewed_script(
    *,
    rubric_snapshot: dict[str, Any],
    template_key: str,
) -> tuple[str, dict[str, Any], dict[str, Any], TeacherJudgeScriptStatus]:
    script_content = await generate_script_content(
        rubric_snapshot=rubric_snapshot,
        template_key=template_key,
    )
    policy_check = check_script_policy(script_content)
    ai_review = await review_script_with_ai(
        script_content=script_content,
        rubric_snapshot=rubric_snapshot,
    )
    status = _resolve_status(policy_check, ai_review)
    return script_content, policy_check, ai_review, status


def list_artifacts(
    *,
    session: Session,
    group_id: uuid.UUID,
) -> list[TeacherJudgeScriptArtifactPublic]:
    artifacts = session.exec(
        select(TeacherJudgeScriptArtifact)
        .where(TeacherJudgeScriptArtifact.group_id == group_id)
        .order_by(desc(TeacherJudgeScriptArtifact.created_at))
    ).all()
    return [_artifact_to_public(artifact) for artifact in artifacts]


def get_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> TeacherJudgeScriptArtifact:
    artifact = session.get(TeacherJudgeScriptArtifact, artifact_id)
    if artifact is None or artifact.group_id != group_id:
        raise HTTPException(status_code=404, detail="Script artifact not found")
    return artifact


def get_artifact_public(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> TeacherJudgeScriptArtifactPublic:
    return _artifact_to_public(
        get_artifact(session=session, group_id=group_id, artifact_id=artifact_id)
    )


def _next_artifact_version(
    *,
    session: Session,
    artifact: TeacherJudgeScriptArtifact,
) -> int:
    max_version = session.exec(
        select(func.max(TeacherJudgeScriptArtifact.version)).where(
            TeacherJudgeScriptArtifact.group_id == artifact.group_id,
            TeacherJudgeScriptArtifact.name == artifact.name,
            TeacherJudgeScriptArtifact.template_key == artifact.template_key,
        )
    ).one()
    return int(max_version or artifact.version) + 1


async def create_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    name: str,
    template_key: str,
    rubric_analysis: RubricAnalysis,
    created_by: uuid.UUID | None,
    template_commands: list[TeacherJudgeTemplateCommand] | None = None,
) -> TeacherJudgeScriptArtifactPublic:
    artifact_name = name.strip()
    if not artifact_name:
        raise HTTPException(status_code=400, detail="腳本名稱不可空白。")

    if template_commands is None:
        template_commands = get_enabled_template_commands(session, template_key)

    rubric_snapshot = _with_template_command_catalog(
        _rubric_snapshot(rubric_analysis, template_key),
        template_commands,
    )
    script_content, policy_check, ai_review, status = await build_reviewed_script(
        rubric_snapshot=rubric_snapshot,
        template_key=template_key,
    )

    artifact = TeacherJudgeScriptArtifact(
        group_id=group_id,
        name=artifact_name,
        template_key=template_key,
        rubric_snapshot_json=rubric_snapshot,
        script_language=TeacherJudgeScriptLanguage.python,
        script_content=script_content,
        source=TeacherJudgeScriptSource.ai_generated,
        version=1,
        status=status,
        policy_check_result_json=policy_check,
        ai_review_result_json=ai_review,
        created_by=created_by,
        updated_at=_now(),
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_to_public(artifact)


async def regenerate_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
    rubric_analysis: RubricAnalysis | None,
    created_by: uuid.UUID | None,
    template_commands: list[TeacherJudgeTemplateCommand] | None = None,
) -> TeacherJudgeScriptArtifactPublic:
    artifact = get_artifact(
        session=session,
        group_id=group_id,
        artifact_id=artifact_id,
    )
    if artifact.status == TeacherJudgeScriptStatus.archived:
        raise HTTPException(status_code=400, detail="已封存的腳本不能重新生成。")
    template_key = artifact.template_key
    if template_commands is None:
        template_commands = get_enabled_template_commands(session, template_key)

    rubric_snapshot = _with_template_command_catalog(
        _rubric_snapshot(rubric_analysis, template_key)
        if rubric_analysis is not None
        else artifact.rubric_snapshot_json,
        template_commands,
    )
    generation_snapshot = dict(rubric_snapshot)
    previous_feedback = _previous_review_feedback(artifact)
    if previous_feedback:
        generation_snapshot["previous_review_feedback"] = previous_feedback
    script_content, policy_check, ai_review, status = await build_reviewed_script(
        rubric_snapshot=generation_snapshot,
        template_key=template_key,
    )

    if artifact.status == TeacherJudgeScriptStatus.approved:
        next_version = _next_artifact_version(session=session, artifact=artifact)
        next_artifact = TeacherJudgeScriptArtifact(
            group_id=group_id,
            name=artifact.name,
            template_key=template_key,
            rubric_snapshot_json=rubric_snapshot,
            script_language=TeacherJudgeScriptLanguage.python,
            script_content=script_content,
            source=TeacherJudgeScriptSource.regenerated,
            version=next_version,
            status=status,
            policy_check_result_json=policy_check,
            ai_review_result_json=ai_review,
            created_by=created_by,
            updated_at=_now(),
        )
        session.add(next_artifact)
        session.commit()
        session.refresh(next_artifact)
        return _artifact_to_public(next_artifact)

    artifact.rubric_snapshot_json = rubric_snapshot
    artifact.script_content = script_content
    artifact.source = TeacherJudgeScriptSource.regenerated
    artifact.status = status
    artifact.policy_check_result_json = policy_check
    artifact.ai_review_result_json = ai_review
    artifact.updated_at = _now()
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_to_public(artifact)


def approve_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
    approved_by: uuid.UUID | None,
) -> TeacherJudgeScriptArtifactPublic:
    artifact = get_artifact(
        session=session,
        group_id=group_id,
        artifact_id=artifact_id,
    )
    if artifact.status != TeacherJudgeScriptStatus.reviewed:
        raise HTTPException(status_code=400, detail="只有審查通過的腳本可以核准。")
    if artifact.policy_check_result_json.get("approved") is not True:
        raise HTTPException(status_code=400, detail="腳本未通過 hard policy。")
    if artifact.ai_review_result_json.get("approved") is not True:
        raise HTTPException(status_code=400, detail="腳本未通過 AI reviewer。")

    artifact.status = TeacherJudgeScriptStatus.approved
    artifact.approved_by = approved_by
    artifact.approved_at = _now()
    artifact.updated_at = _now()
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_to_public(artifact)


def archive_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> TeacherJudgeScriptArtifactPublic:
    artifact = get_artifact(
        session=session,
        group_id=group_id,
        artifact_id=artifact_id,
    )
    artifact.status = TeacherJudgeScriptStatus.archived
    artifact.updated_at = _now()
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_to_public(artifact)


def delete_artifact(
    *,
    session: Session,
    group_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> None:
    artifact = get_artifact(
        session=session,
        group_id=group_id,
        artifact_id=artifact_id,
    )
    session.delete(artifact)
    session.commit()
