from fastapi import APIRouter

from app.api.routes import login, lxc, private, resources, users, utils, vm
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(resources.router)
api_router.include_router(vm.router)
api_router.include_router(lxc.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
