from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.api.ingest import get_ingestion_service, router as ingest_router
from backend.app.api.jobs import (
    get_job_repository,
    get_job_service,
    router as jobs_router,
)
from backend.app.core.config import settings
from backend.app.services.recovery_service import JobRecoveryService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.job_recovery_enabled:
        try:
            repo = get_job_repository()
            ingest = get_ingestion_service()
            service = get_job_service(repo, ingest)
            recovery = JobRecoveryService(
                repo,
                service,
                stale_timeout_seconds=settings.job_stale_timeout_seconds,
            )
            summary = await recovery.recover_interrupted_jobs(force_active=False)
            if summary.recovered_count > 0:
                logger.info(
                    "Startup job recovery: %d stale jobs recovered out of %d active",
                    summary.recovered_count,
                    summary.total_active_scanned,
                )
        except Exception as exc:
            logger.warning("Startup job recovery skipped or encountered an issue: %s", exc)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router, prefix="/v1")
app.include_router(ingest_router)
app.include_router(jobs_router)

