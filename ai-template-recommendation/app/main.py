from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.resources import router as resources_router
from app.core.config import settings
from app.main_state import catalog
from app.services.catalog_service import serialize_template


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(
    title="Campus Template Recommendation",
    description="Layered backend for AI-driven template and sizing recommendation.",
)

app.include_router(recommendation_router)
app.include_router(resources_router, prefix=settings.api_v1_str)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
@app.get(f"{settings.api_v1_str}/health")
def health() -> dict:
    return {
        "status": "ok",
        "templates_loaded": len(catalog.items),
        "templates_dir": str(settings.resolved_templates_dir),
        "use_internal_nodes_api": settings.use_internal_nodes_api,
        "nodes_snapshot_count": len(settings.parsed_nodes_snapshot),
        "vllm_configured": bool(settings.vllm_model_name),
    }


@app.get("/ui-config")
def ui_config() -> dict:
    return {
        "api_base_url": settings.frontend_api_base_url.rstrip("/"),
        "use_internal_nodes_api": settings.use_internal_nodes_api,
    }


@app.get("/catalog/preview")
@app.get(f"{settings.api_v1_str}/catalog/preview")
def catalog_preview(limit: int = 10) -> dict:
    return {
        "count": len(catalog.items),
        "items": [serialize_template(item) for item in catalog.items[:limit]],
    }
