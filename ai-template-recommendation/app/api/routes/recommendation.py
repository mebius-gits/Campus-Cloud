from __future__ import annotations

from fastapi import APIRouter, Request

from app.main_state import catalog
from app.schemas.recommendation import RecommendationRequest
from app.services.backend_nodes_service import fetch_backend_node_payload, normalize_node_payload
from app.services.recommendation_service import generate_ai_plan, normalize_ai_result


router = APIRouter(tags=["recommendation"])


@router.post("/recommend")
@router.post("/api/v1/recommend")
async def recommend(request: RecommendationRequest, http_request: Request):
    payload = await fetch_backend_node_payload(http_request.headers.get("Authorization"))
    live_nodes = normalize_node_payload(payload)
    merged_request = RecommendationRequest(
        **{
            **request.model_dump(),
            "device_nodes": live_nodes or request.device_nodes,
            "top_k": request.top_k,
        }
    )

    ai_result, ai_metrics = await generate_ai_plan(merged_request, merged_request.device_nodes, catalog)
    result = normalize_ai_result(ai_result, merged_request, merged_request.device_nodes, catalog)
    result["live_device_nodes"] = [node.model_dump() for node in merged_request.device_nodes]
    result["ai_metrics"] = ai_metrics
    return result

