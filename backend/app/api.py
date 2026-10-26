from http import HTTPStatus

from fastapi import APIRouter

from app.core.errors import error_responses
from app.features.health.router import router as health_router

api_router = APIRouter(prefix="/api", responses=error_responses(HTTPStatus.INTERNAL_SERVER_ERROR))
api_router.include_router(health_router)
