from fastapi import FastAPI
from backend.app.core.config import settings
from backend.app.api.health import router as health_router

app = FastAPI(title=settings.app_name)

app.include_router(health_router, prefix="/v1")
