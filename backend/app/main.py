from fastapi import FastAPI
from backend.app.core.config import settings

app = FastAPI(title=settings.app_name)

@app.get("/v1/health")
def health_check():
    return {"status": "healthy"}
