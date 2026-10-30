from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import baselines, blockchain, imports, market, portfolio, provenance, reports
from app.services.evidence_store import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.7.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(baselines.router)
app.include_router(blockchain.router)
app.include_router(imports.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(provenance.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"app": settings.app_name, "status": "online", "version": "0.7.0"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": "FastAPI",
        "simulation_brain": "online",
        "provenance_store": "online",
        "version": "0.7.0",
    }
