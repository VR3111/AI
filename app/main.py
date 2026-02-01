from fastapi import FastAPI

from app.ingest_api import router as ingest_router
from app.read_api import router as read_router

app = FastAPI(title="P1 Internal Assistant")

@app.get("/")
def health():
    return {"status": "running"}

# Mount API routers
app.include_router(ingest_router)
app.include_router(read_router)
