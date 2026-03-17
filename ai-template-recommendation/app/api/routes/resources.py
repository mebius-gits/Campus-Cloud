from __future__ import annotations

from fastapi import APIRouter

from app.services.backend_nodes_service import fetch_backend_node_payload, to_public_node_schema


router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/nodes")
async def list_nodes():
    payload = await fetch_backend_node_payload()
    return to_public_node_schema(payload)

