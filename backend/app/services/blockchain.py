from __future__ import annotations

import math
from uuid import uuid4

from app.services.evidence_store import (
    best_hash_baseline,
    create_result,
    nearest_merkle_baseline,
    nearest_pow_baseline,
)


def _baseline_for_algorithm(algorithm: str) -> tuple[float, str]:
    stored = best_hash_baseline(algorithm)
    if not stored:
        raise ValueError(
            "No hay una línea base importada para este algoritmo. "
            "Importe primero una campaña compatible desde la sección Evidencia."
        )
    return stored


def simulate_hash_workload(algorithm: str, transactions: int, hashes_per_transaction: int, band_pct: float = 15.0) -> dict:
    rate, parent_id = _baseline_for_algorithm(algorithm)
    ops = transactions * hashes_per_transaction
    seconds = ops / rate
    band = band_pct / 100
    result_id = f"pcs:hash-estimate:{uuid4().hex[:20]}"
    value = {
        "baseline_ops_sec": rate,
        "transactions": transactions,
        "hashes_per_transaction": hashes_per_transaction,
        "total_operations": ops,
        "estimated_seconds": seconds,
        "lower_seconds": seconds * (1 - band),
        "upper_seconds": seconds * (1 + band),
    }
    create_result(
        result_id=result_id,
        source_artifact_id=None,
        evidence_class="ESTIMATED",
        result_type="hash_workload_estimate",
        metric="estimated_seconds",
        unit="s",
        value=value,
        parameters={"algorithm": algorithm, "transactions": transactions, "hashes_per_transaction": hashes_per_transaction, "conservative_band_pct": band_pct},
        environment={"engine": "Prime ChainSentinel blockchain service"},
        validity_domain={"algorithm": algorithm, "baseline_result_id": parent_id, "use": "offline workload estimation"},
        derived_from=[parent_id],
        transformation="operations_divided_by_measured_hash_rate",
        notes="Estimated from an imported measured CPU cryptographic hash baseline.",
    )
    return {
        "result_id": result_id,
        "schema_version": "1.0.0",
        "evidence_class": "ESTIMATED",
        "derived_from": [parent_id],
        "algorithm": algorithm,
        "data_label": "simulated_from_imported_measured_baseline",
        **value,
        "interpretation": "Estimación derivada de una línea base criptográfica de CPU importada y medida.",
    }


def _next_power_of_two(n: int) -> int:
    return 1 << (n - 1).bit_length()


def _nearest_overhead(algorithm: str, leaves: int) -> tuple[float, str | None]:
    stored = nearest_merkle_baseline(algorithm, leaves)
    if not stored:
        return 1.0, None
    row, result_id = stored
    overhead = row.get("residual_overhead_factor") or row.get("overhead")
    try:
        return float(overhead), result_id
    except (TypeError, ValueError):
        return 1.0, result_id


def simulate_merkle(algorithm: str, transaction_count: int, model: str = "overhead_adjusted") -> dict:
    rate, hash_parent = _baseline_for_algorithm(algorithm)
    leaf_hashes = _next_power_of_two(transaction_count)
    internal_nodes = leaf_hashes - 1
    total_ops = leaf_hashes + internal_nodes
    depth = int(math.ceil(math.log2(transaction_count)))
    naive_ms = (internal_nodes / rate) * 1000
    corrected_ms = (total_ops / rate) * 1000
    overhead, overhead_parent = _nearest_overhead(algorithm, leaf_hashes)
    if model == "overhead_adjusted" and not overhead_parent:
        raise ValueError(
            "No hay una medición Merkle importada para calibrar el sobrecosto. "
            "Importe primero una campaña que contenga merkle_benchmark.csv."
        )
    adjusted_ms = corrected_ms * overhead
    chosen = {"naive": naive_ms, "corrected": corrected_ms, "overhead_adjusted": adjusted_ms}.get(model, adjusted_ms)

    evidence_class = "ESTIMATED" if model == "naive" else "CORRECTED"
    parents = [hash_parent]
    if model == "overhead_adjusted" and overhead_parent and overhead_parent not in parents:
        parents.append(overhead_parent)

    result_id = f"pcs:merkle:{uuid4().hex[:20]}"
    value = {
        "naive_ms": naive_ms,
        "corrected_ms": corrected_ms,
        "residual_overhead_factor": overhead,
        "overhead_adjusted_ms": adjusted_ms,
        "selected_estimated_ms": chosen,
    }
    create_result(
        result_id=result_id,
        source_artifact_id=None,
        evidence_class=evidence_class,
        result_type="merkle_estimate",
        metric="selected_estimated_ms",
        unit="ms",
        value=value,
        parameters={"algorithm": algorithm, "transaction_count": transaction_count, "leaf_hashes": leaf_hashes, "internal_nodes": internal_nodes, "total_hash_operations": total_ops, "tree_depth": depth, "model": model},
        environment={"engine": "Prime ChainSentinel Merkle model"},
        validity_domain={"algorithm": algorithm, "transaction_count": transaction_count, "model": model, "extrapolation": "not assumed beyond recorded baseline domain"},
        derived_from=parents,
        transformation="Merkle structural estimate" if model != "overhead_adjusted" else "Merkle structural estimate plus measured residual overhead",
        notes="The estimate preserves imported measured baselines and overhead calibration as separate antecedents.",
    )

    return {
        "result_id": result_id,
        "schema_version": "1.0.0",
        "evidence_class": evidence_class,
        "derived_from": parents,
        "algorithm": algorithm,
        "data_label": "corrected_estimate" if model != "naive" else "naive_estimate",
        "transaction_count": transaction_count,
        "leaf_hashes": leaf_hashes,
        "internal_nodes": internal_nodes,
        "total_hash_operations": total_ops,
        "tree_depth": depth,
        "hash_rate_ops_sec": rate,
        **value,
        "selected_model": model,
        "interpretation": "El modelo ingenuo cuenta nodos internos; el corregido cuenta hojas y nodos internos; el ajustado añade el sobrecosto observado en evidencia importada.",
    }


def simulate_pow(difficulty_bits: int, seconds: float, hash_rate: float | None = None) -> dict:
    stored = nearest_pow_baseline(difficulty_bits)
    if not stored:
        raise ValueError(
            "No hay evidencia PoW importada. Importe primero una campaña que contenga pow_benchmark.csv."
        )
    baseline_row, parent_id = stored
    if hash_rate is None:
        try:
            hash_rate = float(baseline_row.get("mean_hash_rate_ops_sec") or baseline_row.get("hash_rate"))
        except (TypeError, ValueError):
            hash_rate = None
    if not hash_rate or hash_rate <= 0:
        raise ValueError("La línea base PoW importada no contiene una tasa hash utilizable.")

    expected_trials = 2 ** difficulty_bits
    expected_seconds = expected_trials / hash_rate
    attempts = hash_rate * seconds
    p_single = 2 ** (-difficulty_bits)
    probability = 1 - math.exp(attempts * math.log1p(-p_single))
    result_id = f"pcs:pow-sim:{uuid4().hex[:20]}"
    value = {
        "hash_rate_ops_sec": hash_rate,
        "expected_trials": expected_trials,
        "expected_seconds": expected_seconds,
        "attempts_in_window": attempts,
        "time_window_seconds": seconds,
        "probability_success_by_window": probability,
    }
    create_result(
        result_id=result_id,
        source_artifact_id=None,
        evidence_class="SIMULATED",
        result_type="pow_simulation",
        metric="probability_success_by_window",
        unit="probability",
        value=value,
        parameters={"difficulty_bits": difficulty_bits, "seconds": seconds, "hash_rate": hash_rate},
        environment={"engine": "offline educational PoW simulator"},
        validity_domain={"mode": "offline educational toy PoW", "not_equivalent_to": "live cryptocurrency mining", "difficulty_bits": difficulty_bits},
        derived_from=[parent_id],
        transformation="offline PoW probability model",
        notes="No live mining, pools or payouts.",
    )
    return {
        "result_id": result_id,
        "schema_version": "1.0.0",
        "evidence_class": "SIMULATED",
        "derived_from": [parent_id],
        "difficulty_bits": difficulty_bits,
        "data_label": "offline_toy_simulation",
        **value,
        "safety_boundary": "Simulación educativa fuera de línea. No realiza minería real, no usa pools ni genera pagos.",
    }
