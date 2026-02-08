import sentry_sdk
from fastapi import FastAPI, WebSocket
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.api.websocket import vnc_proxy
from app.api.websocket.terminal import terminal_proxy
from app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.websocket("/ws/vnc/{vmid}")
async def websocket_vnc_proxy(websocket: WebSocket, vmid: int):
    await vnc_proxy(websocket, vmid)


@app.websocket("/ws/terminal/{vmid}")
async def websocket_terminal_proxy(websocket: WebSocket, vmid: int):
    await terminal_proxy(websocket, vmid)
