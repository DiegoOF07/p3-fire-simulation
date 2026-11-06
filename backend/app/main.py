from fastapi import FastAPI

app = FastAPI(title="Fire Sim")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
