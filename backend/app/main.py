from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import kpis

app = FastAPI(title="As Plastique API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kpis.router)

@app.get("/api/ping")
def ping():
    return {"status": "ok", "message": "Backend connecté"}