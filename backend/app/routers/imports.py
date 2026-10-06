from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.evidence_store import get_import, list_imports
from app.services.ingestion import ingest_upload

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("")
async def create_import(file: UploadFile = File(...), campaign: str | None = Form(default=None)):
    try:
        data = await file.read()
        return ingest_upload(file.filename or "upload.bin", data, file.content_type, campaign)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def imports(limit: int = 100):
    return {"items": list_imports(limit=limit)}


@router.get("/{import_id}")
def import_detail(import_id: str):
    item = get_import(import_id)
    if not item:
        raise HTTPException(status_code=404, detail="Import not found")
    return item
