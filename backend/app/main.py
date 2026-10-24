import base64
import binascii
from contextlib import asynccontextmanager
from hmac import compare_digest
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
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


@app.middleware("http")
async def optional_demo_auth(request: Request, call_next):
    """Optional shared HTTP Basic Auth for a single-user thesis demonstration.

    /health stays public so the hosting service can check readiness.
    """
    if request.url.path == "/health":
        return await call_next(request)

    username = os.getenv("PCS_DEMO_USERNAME", "")
    password = os.getenv("PCS_DEMO_PASSWORD", "")
    if username or password:
        if not username or not password:
            return Response("Demo credentials are incomplete", status_code=503)
        supplied_user = supplied_password = ""
        try:
            scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
            if scheme.lower() == "basic":
                decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
                supplied_user, supplied_password = decoded.split(":", 1)
        except (ValueError, UnicodeError, binascii.Error):
            pass
        if not (
            compare_digest(supplied_user, username)
            and compare_digest(supplied_password, password)
        ):
            return Response(
                "Authentication required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Prime ChainSentinel"'},
            )
    return await call_next(request)


app.include_router(baselines.router)
app.include_router(blockchain.router)
app.include_router(imports.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(provenance.router)
app.include_router(reports.router)




@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": "FastAPI",
        "simulation_brain": "online",
        "provenance_store": "online",
        "version": "0.7.0",
    }

# Serve the Vite build at the same origin as the API in Docker.
# When running locally without a build, retain the original API root.
static_dir = Path(__file__).resolve().parents[1] / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"app": settings.app_name, "status": "online", "version": "0.7.0"}
