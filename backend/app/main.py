from fastapi import FastAPI
from backend.app.core.config import settings
from backend.app.api.health import router as health_router
from backend.app.api.ingest import router as ingest_router

app = FastAPI(title=settings.app_name)

app.include_router(health_router, prefix="/v1")
app.include_router(ingest_router)
