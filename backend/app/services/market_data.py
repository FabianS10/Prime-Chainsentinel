from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from app.services.evidence_store import create_result, get_result, upsert_source_artifact

CACHE_DIR = Path("storage/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Deterministic offline fallback characteristics. These are synthetic and are never
# presented as observed market history.
ASSET_PROFILES = {
    "VTI": {"name": "Vanguard Total Stock Market ETF", "mu": 0.075, "sigma": 0.16, "price": 300.0, "kind": "ETF Core"},
    "QQQ": {"name": "Invesco QQQ Trust", "mu": 0.095, "sigma": 0.23, "price": 520.0, "kind": "Growth Tilt"},
    "PLTR": {"name": "Palantir Technologies", "mu": 0.14, "sigma": 0.52, "price": 125.0, "kind": "High-Volatility Satellite"},
    "LMT": {"name": "Lockheed Martin", "mu": 0.065, "sigma": 0.21, "price": 460.0, "kind": "Defense / Industrial"},
    "SPY": {"name": "SPDR S&P 500 ETF Trust", "mu": 0.073, "sigma": 0.17, "price": 620.0, "kind": "Benchmark"},
    "BTC-USD": {"name": "Bitcoin USD", "mu": 0.18, "sigma": 0.75, "price": 100000.0, "kind": "Speculative Crypto"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ticker_seed(ticker: str) -> int:
    # Stable deterministic seed across Python processes.
    return int.from_bytes(ticker.upper().encode("utf-8"), "little", signed=False) % (2**32)


def _cache_path(ticker: str, years: int, source: str) -> Path:
    safe_ticker = ticker.upper().replace("/", "-").replace("^", "IDX-")
    return CACHE_DIR / f"{safe_ticker}_{source}_{years}y_history.json"


def _read_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_fresh(payload: dict, ttl_minutes: int) -> bool:
    stamp = payload.get("retrieved_at") or payload.get("generated_at")
    if not stamp:
        return False
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return _utc_now() - dt <= timedelta(minutes=max(ttl_minutes, 0))
    except ValueError:
        return False


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def generate_offline_history(ticker: str, years: int = 5) -> pd.DataFrame:
    t = ticker.upper()
    profile = ASSET_PROFILES.get(t, {"name": t, "mu": 0.07, "sigma": 0.25, "price": 100.0, "kind": "Manual / Unknown"})
    trading_days = max(252, years * 252)
    rng = np.random.default_rng(_ticker_seed(t))
    dt = 1 / 252
    mu = profile["mu"]
    sigma = profile["sigma"]
    shocks = rng.normal(0, 1, size=trading_days)
    if trading_days > 600:
        start = trading_days // 2
        shocks[start:start + 45] -= 0.55
    log_returns = (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * shocks
    prices = profile["price"] * np.exp(np.cumsum(log_returns))
    dates = pd.bdate_range(end=_utc_now().date(), periods=trading_days)
    return pd.DataFrame({"date": dates, "adjusted_close": prices, "ticker": t})


def _yahoo_history(ticker: str, years: int) -> pd.DataFrame:
    errors: list[str] = []

    try:
        import yfinance as yf

        frame = yf.download(
            tickers=ticker,
            period=f"{years}y",
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
            timeout=20,
        )
        if frame is not None and not frame.empty:
            if isinstance(frame.columns, pd.MultiIndex):
                flattened = []
                for col in frame.columns:
                    parts = [str(x) for x in col if x not in (None, "")]
                    field = next((x for x in parts if x in {"Adj Close", "Close", "Open", "High", "Low", "Volume"}), parts[0])
                    flattened.append(field)
                frame.columns = flattened

            price_column = "Adj Close" if "Adj Close" in frame.columns else "Close" if "Close" in frame.columns else None
            if price_column is not None:
                result = frame[[price_column]].copy().reset_index()
                date_column = "Date" if "Date" in result.columns else result.columns[0]
                result = result.rename(columns={date_column: "date", price_column: "adjusted_close"})
                result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce").dt.tz_convert(None)
                result["adjusted_close"] = pd.to_numeric(result["adjusted_close"], errors="coerce")
                result = result.dropna(subset=["date", "adjusted_close"])
                result = result[result["adjusted_close"] > 0]
                result["ticker"] = ticker.upper()
                if len(result) >= 30:
                    return result
        errors.append("yfinance returned no usable adjusted-close history")
    except Exception as exc:
        errors.append(f"yfinance: {exc}")

    # Direct Yahoo chart endpoint fallback. This does not require a crumb or API key
    # and protects the app when yfinance changes its internal transport layer.
    try:
        import requests
        from urllib.parse import quote

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='-_.')}"
        response = requests.get(
            url,
            params={
                "range": f"{years}y",
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            },
            headers={"User-Agent": "Mozilla/5.0 ChainSentinel/0.4 research dashboard"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        result_obj = payload.get("chart", {}).get("result", [None])[0]
        if not result_obj:
            raise RuntimeError(payload.get("chart", {}).get("error") or "empty Yahoo chart response")
        timestamps = result_obj.get("timestamp") or []
        indicators = result_obj.get("indicators", {})
        adjclose_rows = indicators.get("adjclose") or []
        quote_rows = indicators.get("quote") or []
        prices = (adjclose_rows[0].get("adjclose") if adjclose_rows else None)
        if not prices and quote_rows:
            prices = quote_rows[0].get("close")
        if not timestamps or not prices:
            raise RuntimeError("Yahoo chart response lacked timestamps or prices")
        rows = []
        for ts, price in zip(timestamps, prices):
            if price is None:
                continue
            rows.append({
                "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None),
                "adjusted_close": float(price),
                "ticker": ticker.upper(),
            })
        result = pd.DataFrame(rows)
        if len(result) < 30:
            raise RuntimeError(f"Yahoo chart endpoint returned too few observations: {len(result)}")
        return result
    except Exception as exc:
        errors.append(f"Yahoo chart endpoint: {exc}")

    raise RuntimeError("; ".join(errors))




def _with_provenance(payload: dict) -> dict:
    """Attach and persist provenance for a market-series snapshot.

    The digest proves the exact normalized series used by the application. It does
    not constitute a cryptographic attestation from Yahoo Finance.
    """
    rows = payload.get("history") or []
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = sha256(canonical).hexdigest()
    ticker = payload.get("ticker", "UNKNOWN")
    provider = payload.get("provider", "offline")
    evidence_class = "MEASURED" if provider == "yahoo" else "SIMULATED"
    result_id = f"pcs:market:{ticker}:{digest[:20]}"
    artifact_id = f"pcs:artifact:market:{ticker}:{digest[:20]}"

    origin_status = "EXTERNAL_PROVIDER_RECORDED" if provider == "yahoo" else "INTERNAL_SYNTHETIC_GENERATOR"
    upsert_source_artifact(
        artifact_id=artifact_id,
        import_id=None,
        logical_path=f"{provider}://{ticker}?years={payload.get('years_requested')}",
        stored_path=None,
        media_type="application/json",
        size_bytes=len(canonical),
        digest=digest,
        source_type="external_market_snapshot" if provider == "yahoo" else "synthetic_market_snapshot",
        evidence_class=evidence_class,
        validation_status="VALID",
        origin_status=origin_status,
        metadata={
            "provider": provider,
            "adapter": payload.get("adapter"),
            "retrieved_at": payload.get("retrieved_at"),
            "first_observation": payload.get("first_observation"),
            "last_observation": payload.get("last_observation"),
            "observation_count": payload.get("observation_count"),
            "assurance_note": "Digest records the exact normalized series used by Prime ChainSentinel; it is not a provider-signed attestation.",
        },
    )
    derived_from = []
    if provider != "yahoo":
        generator_id = f"pcs:generator:offline-market:{ticker}"
        create_result(
            result_id=generator_id,
            source_artifact_id=artifact_id,
            evidence_class="EXPERIMENTAL",
            result_type="synthetic_market_generator",
            metric=None,
            unit=None,
            value={"generator": "deterministic geometric random walk fallback"},
            parameters={"ticker": ticker, "years_requested": payload.get("years_requested")},
            environment={"engine": "Prime ChainSentinel offline market fallback"},
            validity_domain={"use": "software continuity only", "not_equivalent_to": "observed market history"},
            notes="Configuration record used as the antecedent of the synthetic market series.",
        )
        derived_from = [generator_id]

    create_result(
        result_id=result_id,
        source_artifact_id=artifact_id if evidence_class == "MEASURED" else None,
        evidence_class=evidence_class,
        result_type="market_series",
        metric="adjusted_close_series",
        unit="currency units",
        value={
            "ticker": ticker,
            "history_sha256": digest,
            "observation_count": payload.get("observation_count"),
            "first_observation": payload.get("first_observation"),
            "last_observation": payload.get("last_observation"),
            # Persist the normalized series used by downstream financial labs.
            # This prevents Monte Carlo/model comparison from silently acquiring
            # a different market window after the user has already queried one.
            "history": rows,
        },
        parameters={
            "ticker": ticker,
            "years_requested": payload.get("years_requested"),
            "provider": provider,
            "adapter": payload.get("adapter"),
        },
        environment={"retrieved_at": payload.get("retrieved_at"), "mode": payload.get("mode")},
        validity_domain={
            "source": provider,
            "ticker": ticker,
            "period": [payload.get("first_observation"), payload.get("last_observation")],
            "interpretation": "observed external series" if provider == "yahoo" else "synthetic continuity fallback",
        },
        derived_from=derived_from,
        transformation="deterministic synthetic market fallback" if derived_from else "external market acquisition",
        notes=payload.get("usage_note"),
    )
    payload["dataset_id"] = result_id
    payload["source_artifact_id"] = artifact_id
    payload["series_sha256"] = digest
    payload["evidence_class"] = evidence_class
    payload["origin_assurance"] = origin_status
    return payload


def _payload_from_frame(ticker: str, years: int, frame: pd.DataFrame, *, provider: str, mode: str, cache_hit: bool, warning: str | None = None) -> dict:
    rows = [
        {"date": str(pd.Timestamp(row.date).date()), "adjusted_close": float(row.adjusted_close)}
        for row in frame.itertuples(index=False)
    ]
    retrieved_at = _utc_now().isoformat()
    is_external = provider == "yahoo"
    payload = {
        "ticker": ticker.upper(),
        "provider": provider,
        "adapter": "yfinance_or_yahoo_chart" if is_external else "internal_deterministic_generator",
        "mode": mode,
        "cache_hit": cache_hit,
        "years_requested": years,
        "retrieved_at": retrieved_at,
        "generated_at": retrieved_at,
        "observation_count": len(rows),
        "first_observation": rows[0]["date"] if rows else None,
        "last_observation": rows[-1]["date"] if rows else None,
        "price_series_label": "MEASURED" if is_external else "SIMULATED",
        "metric_label": "ESTIMATED",
        "source_name": "Yahoo Finance via yfinance / chart endpoint" if is_external else "ChainSentinel deterministic offline fallback",
        "source_home": "https://finance.yahoo.com/" if is_external else None,
        "usage_note": (
            "Serie obtenida mediante el adaptador yfinance para uso académico; debe verificarse la política de la fuente antes de redistribuirla."
            if is_external else
            "Serie sintética de respaldo para continuidad del software; no debe citarse como historia de mercado observada."
        ),
        "warning": warning,
        "history": rows,
    }
    return payload


def get_history(
    ticker: str,
    years: int = 5,
    provider: str = "auto",
    *,
    force_refresh: bool = False,
    cache_ttl_minutes: int = 60,
) -> dict:
    ticker = ticker.upper().strip()
    provider = (provider or "auto").strip().lower()
    if provider not in {"auto", "yahoo", "offline"}:
        raise ValueError(f"Proveedor de datos de mercado no soportado: {provider}")

    if provider in {"auto", "yahoo"}:
        yahoo_cache = _cache_path(ticker, years, "yahoo")
        cached = _read_cache(yahoo_cache)
        if cached and not force_refresh and _is_fresh(cached, cache_ttl_minutes):
            cached["cache_hit"] = True
            cached["mode"] = "yahoo_cache_fresh"
            return _with_provenance(cached)

        try:
            frame = _yahoo_history(ticker, years)
            payload = _payload_from_frame(
                ticker,
                years,
                frame,
                provider="yahoo",
                mode="yahoo_live",
                cache_hit=False,
            )
            payload = _with_provenance(payload)
            _write_cache(yahoo_cache, payload)
            return payload
        except Exception as exc:
            if cached:
                cached["cache_hit"] = True
                cached["mode"] = "yahoo_cache_stale"
                cached["warning"] = f"No fue posible actualizar Yahoo Finance; se utiliza la última serie observada guardada en caché. {exc}"
                return _with_provenance(cached)
            if provider == "yahoo":
                raise RuntimeError(
                    f"No fue posible obtener datos de Yahoo Finance para {ticker} y no existe una serie observada en caché. {exc}"
                ) from exc
            else:
                warning = f"El proveedor en vivo no está disponible; se utilizará el modo sintético configurado como respaldo. {exc}"
        
    else:
        warning = None

    offline_cache = _cache_path(ticker, years, "offline")
    cached_offline = _read_cache(offline_cache)
    if cached_offline and not force_refresh:
        cached_offline["cache_hit"] = True
        cached_offline["mode"] = "offline_cache"
        if warning:
            cached_offline["warning"] = warning
        return _with_provenance(cached_offline)

    frame = generate_offline_history(ticker, years=years)
    payload = _payload_from_frame(
        ticker,
        years,
        frame,
        provider="offline",
        mode="offline_fallback",
        cache_hit=False,
        warning=warning,
    )
    payload = _with_provenance(payload)
    _write_cache(offline_cache, payload)
    return payload


def compute_metrics_from_history(history_payload: dict) -> dict:
    ticker = history_payload["ticker"]
    rows = history_payload["history"]
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No hay observaciones disponibles para {ticker}.")
    df["adjusted_close"] = pd.to_numeric(df["adjusted_close"])
    returns = df["adjusted_close"].pct_change().dropna()
    years = max(len(returns) / 252, 1e-9)
    start = df["adjusted_close"].iloc[0]
    end = df["adjusted_close"].iloc[-1]
    cagr = (end / start) ** (1 / years) - 1
    vol = returns.std(ddof=1) * math.sqrt(252)
    cumulative = df["adjusted_close"] / start
    rolling_max = cumulative.cummax()
    drawdowns = cumulative / rolling_max - 1
    max_drawdown = drawdowns.min()
    profile = ASSET_PROFILES.get(ticker, {"name": ticker, "kind": "Unknown"})
    output = {
        "ticker": ticker,
        "name": profile.get("name", ticker),
        "kind": profile.get("kind", "Unknown"),
        "provider": history_payload.get("provider", "offline"),
        "adapter": history_payload.get("adapter"),
        "mode": history_payload.get("mode", "offline_fallback"),
        "cache_hit": history_payload.get("cache_hit", False),
        "source_name": history_payload.get("source_name"),
        "source_home": history_payload.get("source_home"),
        "usage_note": history_payload.get("usage_note"),
        "warning": history_payload.get("warning"),
        "retrieved_at": history_payload.get("retrieved_at"),
        "dataset_id": history_payload.get("dataset_id"),
        "source_artifact_id": history_payload.get("source_artifact_id"),
        "series_sha256": history_payload.get("series_sha256"),
        "evidence_class": "ESTIMATED",
        "origin_assurance": history_payload.get("origin_assurance"),
        "first_observation": history_payload.get("first_observation"),
        "last_observation": history_payload.get("last_observation"),
        "last_price": float(end),
        "start_price": float(start),
        "cagr": float(cagr),
        "annualized_volatility": float(vol),
        "max_drawdown": float(max_drawdown),
        "mean_daily_return": float(returns.mean()),
        "observations": int(len(df)),
        "price_series_label": history_payload.get("price_series_label", "SIMULATED"),
        "metric_label": "ESTIMATED",
        "data_label": "external_historical_estimate" if history_payload.get("provider") == "yahoo" else "offline_synthetic_estimate",
    }
    dataset_id = history_payload.get("dataset_id")
    digest = history_payload.get("series_sha256", "unknown")
    if dataset_id:
        result_id = f"pcs:market-metrics:{ticker}:{digest[:20]}"
        create_result(
            result_id=result_id,
            source_artifact_id=None,
            evidence_class="ESTIMATED",
            result_type="market_metrics",
            metric="historical_risk_metrics",
            unit=None,
            value={k: output[k] for k in ["cagr", "annualized_volatility", "max_drawdown", "mean_daily_return", "observations"]},
            parameters={"ticker": ticker, "provider": history_payload.get("provider"), "years_requested": history_payload.get("years_requested")},
            environment={"retrieved_at": history_payload.get("retrieved_at")},
            validity_domain={"ticker": ticker, "period": [output["first_observation"], output["last_observation"]], "use": "historical descriptive metrics"},
            derived_from=[dataset_id],
            transformation="prices_to_returns_and_metrics",
            notes="Derived historical metrics; not a direct market measurement by Prime ChainSentinel.",
        )
        output["result_id"] = result_id
        output["derived_from"] = [dataset_id]
    return output



def get_recorded_market_history(result_id: str) -> dict:
    """Reconstruct one exact market snapshot from a persisted market_series result."""
    result = get_result(result_id)
    if not result:
        raise ValueError(f"No existe el resultado de mercado {result_id}.")
    if result.get("result_type") != "market_series":
        raise ValueError(f"El resultado {result_id} no corresponde a una serie de mercado.")
    value = result.get("value") or {}
    rows = value.get("history") or []
    if not rows:
        raise ValueError(
            f"El resultado {result_id} no conserva la serie normalizada. "
            "Vuelve a consultar el mercado con esta versión del software."
        )
    params = result.get("parameters") or {}
    environment = result.get("environment") or {}
    artifact = result.get("source_artifact") or {}
    provider = params.get("provider") or (result.get("validity_domain") or {}).get("source") or "desconocido"
    return {
        "ticker": value.get("ticker") or params.get("ticker"),
        "provider": provider,
        "adapter": params.get("adapter"),
        "mode": environment.get("mode"),
        "cache_hit": False,
        "years_requested": params.get("years_requested"),
        "retrieved_at": environment.get("retrieved_at"),
        "observation_count": value.get("observation_count") or len(rows),
        "first_observation": value.get("first_observation"),
        "last_observation": value.get("last_observation"),
        "price_series_label": result.get("evidence_class"),
        "metric_label": "ESTIMATED",
        "source_name": "Serie registrada en Prime ChainSentinel",
        "source_home": None,
        "usage_note": result.get("notes"),
        "warning": None,
        "history": rows,
        "dataset_id": result_id,
        "source_artifact_id": result.get("source_artifact_id"),
        "series_sha256": value.get("history_sha256") or artifact.get("sha256"),
        "evidence_class": result.get("evidence_class"),
        "origin_assurance": artifact.get("origin_status"),
    }


def portfolio_metrics_from_result_ids(result_ids: list[str]) -> dict:
    """Compute metrics from the exact market-series results chosen by the user."""
    histories: dict[str, dict] = {}
    for result_id in result_ids:
        payload = get_recorded_market_history(result_id)
        ticker = str(payload.get("ticker") or "").upper()
        if not ticker:
            raise ValueError(f"El resultado {result_id} no contiene un símbolo de mercado.")
        histories[ticker] = payload
    if not histories:
        raise ValueError("No se recibieron resultados de mercado registrados.")

    series: dict[str, pd.Series] = {}
    metrics: dict[str, dict] = {}
    for ticker, payload in histories.items():
        df = pd.DataFrame(payload["history"])
        df["date"] = pd.to_datetime(df["date"])
        df["adjusted_close"] = pd.to_numeric(df["adjusted_close"])
        series[ticker] = df.set_index("date")["adjusted_close"].pct_change().dropna().rename(ticker)
        metrics[ticker] = compute_metrics_from_history(payload)

    returns_df = pd.concat(series.values(), axis=1, join="inner").dropna()
    corr = returns_df.corr().fillna(0).to_dict() if not returns_df.empty else {}
    providers = sorted({payload.get("provider", "desconocido") for payload in histories.values()})
    return {
        "metrics": list(metrics.values()),
        "correlation_matrix": corr,
        "provider": providers[0] if len(providers) == 1 else "mixed",
        "providers": providers,
        "warnings": [],
        "price_series_label": "MEASURED" if providers == ["yahoo"] else "MIXED",
        "metric_label": "ESTIMATED",
        "data_label": "recorded_market_metrics",
    }


def get_metrics(
    ticker: str,
    years: int = 5,
    provider: str = "auto",
    *,
    force_refresh: bool = False,
    cache_ttl_minutes: int = 60,
) -> dict:
    hist = get_history(
        ticker,
        years=years,
        provider=provider,
        force_refresh=force_refresh,
        cache_ttl_minutes=cache_ttl_minutes,
    )
    return compute_metrics_from_history(hist)


def portfolio_metrics(
    tickers: list[str],
    years: int = 5,
    provider: str = "auto",
    *,
    force_refresh: bool = False,
    cache_ttl_minutes: int = 60,
) -> dict:
    histories = {
        t.upper(): get_history(
            t,
            years=years,
            provider=provider,
            force_refresh=force_refresh,
            cache_ttl_minutes=cache_ttl_minutes,
        )
        for t in tickers
    }
    series: dict[str, pd.Series] = {}
    metrics: dict[str, dict] = {}
    for t, payload in histories.items():
        df = pd.DataFrame(payload["history"])
        df["date"] = pd.to_datetime(df["date"])
        df["adjusted_close"] = pd.to_numeric(df["adjusted_close"])
        series[t] = df.set_index("date")["adjusted_close"].pct_change().dropna().rename(t)
        metrics[t] = compute_metrics_from_history(payload)

    returns_df = pd.concat(series.values(), axis=1, join="inner").dropna()
    corr = returns_df.corr().fillna(0).to_dict() if not returns_df.empty else {}
    providers = sorted({payload.get("provider", "offline") for payload in histories.values()})
    warnings = [payload.get("warning") for payload in histories.values() if payload.get("warning")]
    return {
        "metrics": list(metrics.values()),
        "correlation_matrix": corr,
        "provider": providers[0] if len(providers) == 1 else "mixed",
        "providers": providers,
        "warnings": warnings,
        "price_series_label": "MEASURED" if providers == ["yahoo"] else "MIXED" if "yahoo" in providers else "SIMULATED",
        "metric_label": "ESTIMATED",
        "data_label": "historical_market_metrics" if providers == ["yahoo"] else "mixed_or_fallback_market_metrics",
    }
