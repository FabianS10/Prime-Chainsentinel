from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.schemas import ReportRequest
from app.services.report import generate_pdf_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("/generate")
def generate(req: ReportRequest):
    path = generate_pdf_report(req)
    return FileResponse(path, media_type="application/pdf", filename=path.name)
