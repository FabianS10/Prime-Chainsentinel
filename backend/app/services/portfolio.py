from __future__ import annotations
import math
import json
from hashlib import sha256
import numpy as np
from app.schemas import PortfolioRequest
from app.services.market_data import portfolio_metrics, portfolio_metrics_from_result_ids
from app.services.evidence_store import create_result


def normalize_weights(weights: np.ndarray) -> np.ndarray:
    s = weights.sum()
    if s <= 0:
        raise ValueError("Los pesos de la cartera deben sumar un valor positivo.")
    return weights / s


def run_monte_carlo(req: PortfolioRequest, provider: str = "offline") -> dict:
    tickers = [a.ticker.upper() for a in req.assets]
    market = (
        portfolio_metrics_from_result_ids(req.market_dataset_ids)
        if req.market_dataset_ids
        else portfolio_metrics(tickers, years=req.market_years, provider=provider)
    )
    available_tickers = {str(m.get("ticker") or "").upper() for m in market.get("metrics", [])}
    requested_tickers = set(tickers)
    if available_tickers != requested_tickers:
        raise ValueError(
            "La evidencia de mercado seleccionada no coincide con los activos de la cartera. "
            "Vuelve al Laboratorio de mercado y realiza una nueva consulta."
        )
    metrics_map = {m["ticker"]: m for m in market["metrics"]}

    weights = normalize_weights(np.array([a.weight for a in req.assets], dtype=float))
    mus = []
    sigmas = []
    for asset in req.assets:
        m = metrics_map.get(asset.ticker.upper())
        mus.append(asset.expected_return if asset.expected_return is not None else m["cagr"])
        sigmas.append(asset.volatility if asset.volatility is not None else m["annualized_volatility"])
    mus = np.array(mus, dtype=float)
    sigmas = np.array(sigmas, dtype=float)

    corr_dict = market["correlation_matrix"]
    corr = np.eye(len(tickers))
    for i, ti in enumerate(tickers):
        for j, tj in enumerate(tickers):
            corr[i, j] = corr_dict.get(ti, {}).get(tj, 1.0 if ti == tj else 0.2)
    # Stabilize in case of numerical issues.
    corr = corr + np.eye(len(tickers)) * 1e-8
    chol = np.linalg.cholesky(corr)

    rng = np.random.default_rng(req.seed)
    months = req.horizon_years * 12
    dt = 1 / 12
    paths = np.zeros((req.trials, months + 1), dtype=float)
    paths[:, 0] = req.initial_capital
    drawdowns = np.zeros(req.trials, dtype=float)

    for t in range(1, months + 1):
        if req.use_student_t:
            z = rng.standard_t(df=5, size=(req.trials, len(tickers))) / math.sqrt(5 / (5 - 2))
        else:
            z = rng.normal(0, 1, size=(req.trials, len(tickers)))
        correlated = z @ chol.T
        asset_returns = (mus - 0.5 * sigmas**2) * dt + sigmas * math.sqrt(dt) * correlated
        simple_returns = np.exp(asset_returns) - 1
        portfolio_returns = simple_returns @ weights
        paths[:, t] = (paths[:, t - 1] + req.monthly_contribution) * (1 + portfolio_returns)

    running_max = np.maximum.accumulate(paths, axis=1)
    dd = paths / running_max - 1
    max_dd = dd.min(axis=1)
    final = paths[:, -1]
    percentiles = {f"p{p}": np.percentile(paths, p, axis=0).round(2).tolist() for p in [5, 10, 25, 50, 75, 90, 95]}
    final_dist = {f"p{p}": float(np.percentile(final, p)) for p in [5, 10, 25, 50, 75, 90, 95]}
    final_dist.update({"mean": float(final.mean()), "median": float(np.median(final))})
    prob_loss = float((final < req.initial_capital).mean())
    prob_target = float((final >= req.target_value).mean()) if req.target_value else None
    portfolio_vol = float(np.sqrt(weights @ (np.outer(sigmas, sigmas) * corr) @ weights))
    p90_drawdown = float(abs(np.percentile(max_dd, 10)))
    cvar95 = float(abs(final[final <= np.percentile(final, 5)].mean() / max(np.median(final), 1) - 1))
    concentration = float(weights.max())
    uncertainty = float((final_dist["p90"] - final_dist["p10"]) / max(final_dist["median"], 1))
    risk_score = min(100, 0.25 * min(100, portfolio_vol / 0.50 * 100) +
                          0.25 * min(100, p90_drawdown / 0.60 * 100) +
                          0.20 * min(100, cvar95 / 0.50 * 100) +
                          0.15 * concentration * 100 +
                          0.10 * min(100, uncertainty * 100) +
                          0.05 * (100 if req.horizon_years < 5 and portfolio_vol > 0.25 else 0))
    label = "Bajo" if risk_score <= 20 else "Moderado" if risk_score <= 40 else "Agresivo" if risk_score <= 60 else "Alta volatilidad" if risk_score <= 80 else "Especulativo / extremo"

    # Downsample sample paths for frontend readability.
    sample_idx = np.linspace(0, req.trials - 1, min(40, req.trials), dtype=int)
    sample_paths = paths[sample_idx].round(2).tolist()

    identity = {
        "assets": [{"ticker": a.ticker.upper(), "weight": float(a.weight)} for a in req.assets],
        "market_years": req.market_years,
        "initial_capital": req.initial_capital,
        "monthly_contribution": req.monthly_contribution,
        "horizon_years": req.horizon_years,
        "trials": req.trials,
        "target_value": req.target_value,
        "seed": req.seed,
        "use_student_t": req.use_student_t,
        "parents": sorted(req.market_dataset_ids or [m.get("dataset_id") for m in market["metrics"] if m.get("dataset_id")]),
    }
    digest = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    simulation_id = f"mc_{digest}"
    result_id = f"pcs:simulation:{simulation_id}"
    parents = list(req.market_dataset_ids or [m.get("dataset_id") for m in market["metrics"] if m.get("dataset_id")])
    result_payload = {
        "simulation_id": simulation_id,
        "data_label": "simulated_from_market_history_or_fallback",
        "assets": [{"ticker": t, "weight": float(w), "mu": float(mu), "sigma": float(s)} for t, w, mu, s in zip(tickers, weights, mus, sigmas)],
        "market_metrics": market["metrics"],
        "correlation_matrix": market["correlation_matrix"],
        "trials": req.trials,
        "months": months,
        "years": req.horizon_years,
        "market_years": req.market_years,
        "percentiles": percentiles,
        "sample_paths": sample_paths,
        "final_value_distribution": final_dist,
        "risk": {
            "risk_score": float(risk_score),
            "risk_label": label,
            "annualized_volatility": portfolio_vol,
            "max_drawdown_p90": p90_drawdown,
            "probability_loss": prob_loss,
            "probability_target_reached": prob_target,
            "uncertainty_spread": uncertainty,
            "largest_position_weight": concentration,
        },
        "interpretation": "Los resultados representan escenarios condicionados por los datos históricos y los parámetros seleccionados; no constituyen una predicción garantizada.",
    }
    if parents:
        create_result(
            result_id=result_id,
            source_artifact_id=None,
            evidence_class="SIMULATED",
            result_type="portfolio_simulation",
            metric="final_value_distribution",
            unit="currency units",
            value={"final_value_distribution": final_dist, "risk": result_payload["risk"]},
            parameters={
                "assets": [{"ticker": a.ticker.upper(), "weight": a.weight} for a in req.assets],
                "market_years": req.market_years,
                "market_dataset_ids": parents,
                "initial_capital": req.initial_capital,
                "monthly_contribution": req.monthly_contribution,
                "horizon_years": req.horizon_years,
                "trials": req.trials,
                "seed": req.seed,
                "use_student_t": req.use_student_t,
            },
            environment={"engine": "Prime ChainSentinel Monte Carlo"},
            validity_domain={"use": "educational portfolio simulation", "not_equivalent_to": "guaranteed future return", "provider": market.get("provider")},
            derived_from=parents,
            transformation="Monte Carlo portfolio simulation",
            notes="Escenarios probabilísticos derivados de evidencia de mercado registrada; no constituyen asesoría financiera.",
        )
        result_payload.update({"result_id": result_id, "schema_version": "1.0.0", "evidence_class": "SIMULATED", "derived_from": parents})
    return result_payload

