from fastapi import FastAPI

app = FastAPI()

@app.get("/v1/health")
def health_check():
    return {"status": "healthy"}
