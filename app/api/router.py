from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.requests import router as requests_router
from app.core.config import get_settings

settings = get_settings()

router = APIRouter()
router.include_router(health_router)
router.include_router(requests_router, prefix=settings.api_v1_prefix)
