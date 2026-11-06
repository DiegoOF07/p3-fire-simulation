from fastapi import FastAPI

from app.api import rest, ws

app = FastAPI(title="Fire Sim")
app.include_router(rest.router)
app.include_router(ws.router)
