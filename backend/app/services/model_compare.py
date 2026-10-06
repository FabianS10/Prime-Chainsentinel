from __future__ import annotations

import math
import json
from hashlib import sha256
from collections import defaultdict

import numpy as np
import pandas as pd

from app.schemas import ModelComparisonRequest
from app.services.market_data import get_history, get_recorded_market_history
from app.services.evidence_store import create_result

MODEL_LABELS = {
    "gaussian_gbm": "GBM gaussiano",
    "student_t": "Monte Carlo Student-t",
    "bootstrap": "Bootstrap temporal",
    "garch_gaussian": "GARCH gaussiano",
    "garch_student_t": "GARCH Student-t",
}


def _normalize_weights(weights: np.ndarray) -> np.ndarray:
    total = weights.sum()
    if total <= 0:
        raise ValueError("Los pesos de la cartera deben sumar un valor positivo.")
    return weights / total


def _pinball_loss(actual: float, forecast: float, q: float) -> float:
    diff = actual - forecast
    return max(q * diff, (q - 1.0) * diff)


def _classify_regime(realized_path: np.ndarray) -> str:
    cumulative = float(np.prod(1.0 + realized_path) - 1.0)
    ann_vol = float(np.std(realized_path, ddof=1) * math.sqrt(12)) if len(realized_path) > 1 else 0.0
    if cumulative <= -0.08:
        return "bear"
    if ann_vol >= 0.28:
        return "volatile"
    if cumulative >= 0.08:
        return "bull"
    return "sideways"


def _simulate_terminal_values(monthly_return_paths: np.ndarray, initial_capital: float, monthly_contribution: float) -> np.ndarray:
    wealth = np.full(monthly_return_paths.shape[0], float(initial_capital), dtype=float)
    for t in range(monthly_return_paths.shape[1]):
        wealth = (wealth + float(monthly_contribution)) * (1.0 + monthly_return_paths[:, t])
    return wealth


def _apply_realized_path(realized_returns: np.ndarray, initial_capital: float, monthly_contribution: float) -> float:
    wealth = float(initial_capital)
    for r in realized_returns:
        wealth = (wealth + float(monthly_contribution)) * (1.0 + float(r))
    return wealth


def _simulate_gaussian(train: np.ndarray, horizon: int, trials: int, rng: np.random.Generator) -> np.ndarray:
    mu = float(train.mean())
    sigma = float(train.std(ddof=1)) if len(train) > 1 else 0.01
    sigma = max(sigma, 1e-6)
    return rng.normal(mu, sigma, size=(trials, horizon))


def _simulate_student_t(train: np.ndarray, horizon: int, trials: int, rng: np.random.Generator) -> np.ndarray:
    mu = float(train.mean())
    sigma = float(train.std(ddof=1)) if len(train) > 1 else 0.01
    sigma = max(sigma, 1e-6)
    df = 5.0
    z = rng.standard_t(df=df, size=(trials, horizon)) / math.sqrt(df / (df - 2.0))
    return mu + sigma * z


def _simulate_bootstrap(train: np.ndarray, horizon: int, trials: int, rng: np.random.Generator) -> np.ndarray:
    idx = rng.integers(0, len(train), size=(trials, horizon))
    return train[idx]


def _simulate_garch(train: np.ndarray, horizon: int, trials: int, rng: np.random.Generator, student_t: bool = False) -> np.ndarray:
    mu = float(train.mean())
    centered = train - mu
    base_var = float(np.var(centered, ddof=1)) if len(centered) > 1 else 0.0004
    base_var = max(base_var, 1e-6)

    alpha = 0.08
    beta = 0.90
    if student_t:
        alpha = 0.07
        beta = 0.91
    persistence = min(alpha + beta, 0.995)
    omega = base_var * max(1.0 - persistence, 1e-4)

    sigma2 = np.full(trials, base_var, dtype=float)
    paths = np.zeros((trials, horizon), dtype=float)
    if len(centered) > 0:
        # Use recent realized shocks to initialize the volatility state.
        recent = centered[-min(12, len(centered)):]
        recent_var = float(np.mean(recent ** 2)) if len(recent) else base_var
        sigma2[:] = max(recent_var, 1e-6)

    for t in range(horizon):
        if student_t:
            df = 6.0
            eps = rng.standard_t(df=df, size=trials) / math.sqrt(df / (df - 2.0))
        else:
            eps = rng.normal(0.0, 1.0, size=trials)
        sigma = np.sqrt(np.maximum(sigma2, 1e-8))
        innovation = sigma * eps
        returns = mu + innovation
        paths[:, t] = returns
        sigma2 = omega + alpha * (innovation ** 2) + beta * sigma2
    return paths


def _aligned_monthly_portfolio_returns(req: ModelComparisonRequest, provider: str) -> tuple[pd.Series, list[str]]:
    tickers = [asset.ticker.upper() for asset in req.assets]
    weights = _normalize_weights(np.array([asset.weight for asset in req.assets], dtype=float))

    merged = None
    source_ids: list[str] = []
    recorded = {}
    if req.market_dataset_ids:
        for result_id in req.market_dataset_ids:
            payload = get_recorded_market_history(result_id)
            recorded[str(payload.get("ticker") or "").upper()] = payload
        if set(recorded) != set(tickers):
            raise ValueError(
                "La evidencia de mercado seleccionada no coincide con los activos de la cartera. "
                "Vuelve al Laboratorio de mercado y realiza una nueva consulta."
            )

    for ticker in tickers:
        payload = recorded.get(ticker) if recorded else get_history(ticker, years=req.years, provider=provider)
        if payload.get("dataset_id"):
            source_ids.append(payload["dataset_id"])
        df = pd.DataFrame(payload["history"])
        if df.empty:
            raise ValueError(f"No hay historia disponible para {ticker}.")
        df["date"] = pd.to_datetime(df["date"])
        df["adjusted_close"] = pd.to_numeric(df["adjusted_close"])
        series = df[["date", "adjusted_close"]].rename(columns={"adjusted_close": ticker})
        merged = series if merged is None else merged.merge(series, on="date", how="inner")

    if merged is None or merged.empty:
        raise ValueError("No fue posible alinear las series históricas de los activos solicitados.")

    merged = merged.sort_values("date").set_index("date")
    daily_returns = merged.pct_change().dropna()
    portfolio_daily = daily_returns.dot(weights)
    monthly = (1.0 + portfolio_daily).resample("ME").prod() - 1.0
    monthly.name = "portfolio_return"
    monthly = monthly.dropna()
    if len(monthly) < req.rolling_window_months + req.forecast_horizon_months + 6:
        raise ValueError(
            f"No hay suficientes observaciones mensuales para esta configuración. "
            f"Se requieren al menos {req.rolling_window_months + req.forecast_horizon_months + 6} "
            f"y solo hay {len(monthly)}. Reduce la ventana de entrenamiento, el horizonte o consulta más años de mercado."
        )
    return monthly, source_ids


def run_model_comparison(req: ModelComparisonRequest, provider: str = "offline") -> dict:
    monthly, source_ids = _aligned_monthly_portfolio_returns(req, provider)
    values = monthly.to_numpy(dtype=float)

    model_fns = {
        "gaussian_gbm": lambda train, horizon, trials, rng: _simulate_gaussian(train, horizon, trials, rng),
        "student_t": lambda train, horizon, trials, rng: _simulate_student_t(train, horizon, trials, rng),
        "bootstrap": lambda train, horizon, trials, rng: _simulate_bootstrap(train, horizon, trials, rng),
        "garch_gaussian": lambda train, horizon, trials, rng: _simulate_garch(train, horizon, trials, rng, student_t=False),
        "garch_student_t": lambda train, horizon, trials, rng: _simulate_garch(train, horizon, trials, rng, student_t=True),
    }

    model_stats = {
        key: {
            "coverage_hits": [],
            "interval_widths": [],
            "quantile_losses": [],
            "cvars": [],
            "terminals": [],
            "regime_rows": defaultdict(list),
        }
        for key in model_fns
    }

    horizon = req.forecast_horizon_months
    eval_count = 0
    for origin in range(req.rolling_window_months, len(values) - horizon + 1):
        train = values[origin - req.rolling_window_months:origin]
        realized_path = values[origin:origin + horizon]
        realized_terminal = _apply_realized_path(realized_path, req.initial_capital, req.monthly_contribution)
        regime = _classify_regime(realized_path)
        eval_count += 1

        for idx, (model_key, fn) in enumerate(model_fns.items()):
            rng = np.random.default_rng(req.seed + origin * 97 + idx * 1009)
            simulated_paths = fn(train, horizon, req.trials, rng)
            simulated_terminals = _simulate_terminal_values(simulated_paths, req.initial_capital, req.monthly_contribution)
            q05 = float(np.quantile(simulated_terminals, 0.05))
            q95 = float(np.quantile(simulated_terminals, 0.95))
            median = float(np.median(simulated_terminals))
            coverage_hit = 1.0 if q05 <= realized_terminal <= q95 else 0.0
            width = q95 - q05
            qloss = 0.5 * (
                _pinball_loss(realized_terminal, q05, 0.05) + _pinball_loss(realized_terminal, q95, 0.95)
            )
            tail = simulated_terminals[simulated_terminals <= q05]
            cvar = float(max(0.0, 1.0 - tail.mean() / max(median, 1e-8))) if len(tail) else 0.0

            stats = model_stats[model_key]
            stats["coverage_hits"].append(coverage_hit)
            stats["interval_widths"].append(width)
            stats["quantile_losses"].append(qloss)
            stats["cvars"].append(cvar)
            stats["terminals"].append(realized_terminal)
            stats["regime_rows"][regime].append(coverage_hit)

    results = []
    regime_chart_rows = []
    latest_projection = []
    full_train = values[-req.rolling_window_months:]

    for idx, (model_key, fn) in enumerate(model_fns.items()):
        stats = model_stats[model_key]
        coverage_rate = float(np.mean(stats["coverage_hits"])) if stats["coverage_hits"] else 0.0
        coverage_error = abs(coverage_rate - 0.90)
        avg_width = float(np.mean(stats["interval_widths"])) if stats["interval_widths"] else 0.0
        median_terminal_obs = float(np.median(stats["terminals"])) if stats["terminals"] else max(req.initial_capital, 1.0)
        avg_width_pct = avg_width / max(median_terminal_obs, 1.0)
        quantile_loss = float(np.mean(stats["quantile_losses"])) if stats["quantile_losses"] else 0.0
        cvar_pct = float(np.mean(stats["cvars"])) if stats["cvars"] else 0.0

        results.append({
            "model_key": model_key,
            "model": MODEL_LABELS[model_key],
            "coverage_rate": coverage_rate,
            "coverage_error_90": coverage_error,
            "average_interval_width": avg_width,
            "average_interval_width_pct": avg_width_pct,
            "quantile_loss": quantile_loss,
            "cvar_95_pct": cvar_pct,
            "evaluation_windows": len(stats["coverage_hits"]),
            "notes": "Modelo distribucional evaluado mediante validación temporal de origen móvil sobre retornos mensuales de la cartera.",
        })

        regime_chart_rows.append({
            "model": MODEL_LABELS[model_key],
            "bull": float(np.mean(stats["regime_rows"].get("bull", [0.0]))),
            "bear": float(np.mean(stats["regime_rows"].get("bear", [0.0]))),
            "volatile": float(np.mean(stats["regime_rows"].get("volatile", [0.0]))),
            "sideways": float(np.mean(stats["regime_rows"].get("sideways", [0.0]))),
        })

        rng = np.random.default_rng(req.seed + 50_000 + idx * 17)
        latest_paths = fn(full_train, horizon, req.trials, rng)
        latest_terminals = _simulate_terminal_values(latest_paths, req.initial_capital, req.monthly_contribution)
        latest_projection.append({
            "model": MODEL_LABELS[model_key],
            "p10": float(np.quantile(latest_terminals, 0.10)),
            "p50": float(np.quantile(latest_terminals, 0.50)),
            "p90": float(np.quantile(latest_terminals, 0.90)),
        })

    identity = {
        "assets": [{"ticker": a.ticker.upper(), "weight": float(a.weight)} for a in req.assets],
        "initial_capital": req.initial_capital,
        "monthly_contribution": req.monthly_contribution,
        "years": req.years,
        "rolling_window_months": req.rolling_window_months,
        "forecast_horizon_months": req.forecast_horizon_months,
        "trials": req.trials,
        "seed": req.seed,
        "parents": sorted(source_ids),
    }
    digest = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    comparison_id = f"modelcmp_{digest}"
    output = {
        "comparison_id": comparison_id,
        "provider": provider,
        "data_label": "simulated_from_market_history_or_fallback",
        "assets": [{"ticker": a.ticker.upper(), "weight": a.weight} for a in req.assets],
        "years": req.years,
        "rolling_window_months": req.rolling_window_months,
        "forecast_horizon_months": req.forecast_horizon_months,
        "trials": req.trials,
        "seed": req.seed,
        "evaluation_windows": eval_count,
        "summary": results,
        "regime_coverage": regime_chart_rows,
        "latest_projection": latest_projection,
        "regime_labels": {
            "bull": "régimen alcista",
            "bear": "régimen bajista",
            "volatile": "alta volatilidad",
            "sideways": "régimen lateral",
        },
        "notes": [
            "GBM gaussiano y Student-t utilizan estimaciones móviles de retornos mensuales.",
            "El bootstrap temporal remuestrea retornos mensuales históricos sin imponer una distribución paramétrica.",
            "Las variantes GARCH emplean una recursión de volatilidad para la comparación dentro del laboratorio.",
            "Los resultados son diagnósticos educativos de comparación de modelos y no constituyen asesoría financiera.",
        ],
    }
    if source_ids:
        result_id = f"pcs:model-comparison:{comparison_id}"
        create_result(
            result_id=result_id,
            source_artifact_id=None,
            evidence_class="EXPERIMENTAL",
            result_type="model_comparison",
            metric="rolling_origin_diagnostics",
            unit=None,
            value={
                "summary": results,
                "regime_coverage": regime_chart_rows,
                "latest_projection": latest_projection,
                "evaluation_windows": eval_count,
            },
            parameters={
                "assets": output["assets"],
                "market_dataset_ids": source_ids,
                "years": req.years,
                "rolling_window_months": req.rolling_window_months,
                "forecast_horizon_months": req.forecast_horizon_months,
                "trials": req.trials,
                "seed": req.seed,
            },
            environment={"engine": "Prime ChainSentinel model comparison"},
            validity_domain={"use": "educational rolling-origin model diagnostic", "provider": provider},
            derived_from=source_ids,
            transformation="rolling-origin model comparison",
            notes="Artefacto experimental de comparación; no constituye una recomendación de selección de modelo.",
        )
        output.update({"result_id": result_id, "schema_version": "1.0.0", "evidence_class": "EXPERIMENTAL", "derived_from": source_ids})
    return output
