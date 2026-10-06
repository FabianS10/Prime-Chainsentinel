from fastapi import APIRouter, HTTPException

from app.services.evidence_store import (
    get_artifact,
    get_result,
    list_results,
    provenance_summary,
    verify_artifact,
)

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


@router.get("/summary")
def summary():
    return provenance_summary()


@router.get("/results")
def results(limit: int = 100, evidence_class: str | None = None, result_type: str | None = None):
    return {"items": list_results(limit=limit, evidence_class=evidence_class, result_type=result_type)}


@router.get("/results/{result_id:path}")
def result_detail(result_id: str):
    result = get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.get("/artifacts/{artifact_id:path}")
def artifact_detail(artifact_id: str):
    artifact = get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.get("/artifacts/{artifact_id:path}/verify")
def artifact_verify(artifact_id: str):
    try:
        return verify_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
