from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.services.market_data import get_history, get_metrics, portfolio_metrics

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/history/{ticker}")
def history(ticker: str, years: int = 5, refresh: bool = False):
    settings = get_settings()
    return get_history(
        ticker,
        years=years,
        provider=settings.market_data_provider,
        force_refresh=refresh,
        cache_ttl_minutes=settings.market_cache_ttl_minutes,
    )


@router.get("/metrics/{ticker}")
def metrics(ticker: str, years: int = 5, refresh: bool = False):
    settings = get_settings()
    return get_metrics(
        ticker,
        years=years,
        provider=settings.market_data_provider,
        force_refresh=refresh,
        cache_ttl_minutes=settings.market_cache_ttl_minutes,
    )


@router.get("/portfolio-metrics")
def portfolio(tickers: str, years: int = 5, refresh: bool = False):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="Debe indicar al menos un símbolo para consultar el mercado.")
    settings = get_settings()
    return portfolio_metrics(
        ticker_list,
        years=years,
        provider=settings.market_data_provider,
        force_refresh=refresh,
        cache_ttl_minutes=settings.market_cache_ttl_minutes,
    )
