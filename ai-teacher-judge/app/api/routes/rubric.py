from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response

from app.schemas.rubric import RubricChatRequest
from app.services.rubric_parser import parse_document
from app.services.rubric_service import (
    analyze_rubric,
    chat_with_rubric,
    export_to_excel,
    normalize_items_for_export,
)

router = APIRouter(tags=["rubric"])


@router.post("/upload-rubric")
@router.post("/api/v1/upload-rubric")
async def upload_rubric(file: UploadFile = File(...)):
    """上傳評分表文件（.docx / .pdf），AI 解析並回傳結構化評分分析。"""
    filename = file.filename or "unknown"
    allowed = {".docx", ".pdf"}
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"不支援的格式 '{suffix}'，目前接受：{', '.join(allowed)}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上傳的檔案是空的。")

    try:
        raw_text = parse_document(filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="無法從文件中提取任何文字，請確認文件不是掃描版 PDF。")

    analysis, metrics = await analyze_rubric(raw_text)
    return {
        "analysis": analysis.model_dump(),
        "ai_metrics": metrics,
    }


@router.post("/chat")
@router.post("/api/v1/chat")
async def chat(request: RubricChatRequest):
    """與 AI 對話，精煉評分表；rubric_context 帶入目前評分表的 JSON 字串。"""
    reply, updated_items, metrics = await chat_with_rubric(
        request.messages,
        request.rubric_context,
        is_refine=request.is_refine,
    )
    return {
        "reply": reply,
        "updated_items": updated_items,  # None 或更新後的完整 item 列表
        "prompt_tokens": metrics["prompt_tokens"],
        "completion_tokens": metrics["completion_tokens"],
        "total_tokens": metrics["total_tokens"],
        "elapsed_seconds": metrics["elapsed_seconds"],
        "tokens_per_second": metrics["tokens_per_second"],
    }


@router.post("/download-excel")
@router.post("/api/v1/download-excel")
async def download_excel(payload: dict):
    """
    接收 { items: [...RubricItem], summary: str }，
    產出並回傳 .xlsx 檔案。
    """
    raw_items = payload.get("items") or []
    summary = str(payload.get("summary") or "")

    items = normalize_items_for_export(raw_items)

    if not items:
        raise HTTPException(status_code=400, detail="沒有可匯出的評分項目。")

    excel_bytes = export_to_excel(items, summary=summary)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=rubric.xlsx"},
    )
