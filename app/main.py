from fastapi import FastAPI

app = FastAPI(title="P1 Internal Assistant")

@app.get("/")
def health():
    return {"status": "running"}