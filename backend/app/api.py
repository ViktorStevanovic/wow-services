from http import HTTPStatus

from fastapi import APIRouter

from app.core.errors import error_responses
from app.features.auth.router import router as auth_router
from app.features.health.router import router as health_router
from app.features.users.router import router as users_router

api_router = APIRouter(prefix="/api", responses=error_responses(HTTPStatus.INTERNAL_SERVER_ERROR))
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
