from fastapi import APIRouter, HTTPException
from app.core.config import get_settings
from app.schemas import ModelComparisonRequest, PortfolioRequest
from app.services.model_compare import run_model_comparison
from app.services.portfolio import run_monte_carlo

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

@router.post("/monte-carlo")
def monte_carlo(req: PortfolioRequest):
    try:
        return run_monte_carlo(req, provider=get_settings().market_data_provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/model-comparison")
def model_comparison(req: ModelComparisonRequest):
    try:
        return run_model_comparison(req, provider=get_settings().market_data_provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
