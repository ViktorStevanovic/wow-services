from fastapi import APIRouter

from app.features.health.router import router as health_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
