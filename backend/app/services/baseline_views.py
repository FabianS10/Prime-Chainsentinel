from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.evidence_store import (
    get_artifact,
    latest_completed_import,
    list_results_for_import,
)


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _source_meta(result: dict | None, active_import: dict | None) -> dict | None:
    if not result or not result.get("source_artifact_id"):
        return None
    artifact = get_artifact(result["source_artifact_id"])
    if not artifact:
        return None
    return {
        "import_id": artifact.get("import_id"),
        "campaign": (active_import or {}).get("campaign") or (active_import or {}).get("filename"),
        "filename": (active_import or {}).get("filename"),
        "imported_at": (active_import or {}).get("imported_at"),
        "origin_status": (active_import or {}).get("origin_status"),
        "artifact_id": artifact.get("artifact_id"),
        "logical_path": artifact.get("logical_path"),
        "sha256": artifact.get("sha256"),
        "validation_status": artifact.get("validation_status"),
    }


def _preferred_artifact_group(results: list[dict]) -> tuple[list[dict], dict | None]:
    """Choose one campaign file for single-run baseline views.

    Prefer a full run 2 artifact, then full run 1, then any non-smoke artifact.
    The original imported evidence remains intact; this only selects the default
    view used by the UI.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    artifacts: dict[str, dict] = {}
    for result in results:
        aid = result.get("source_artifact_id")
        if not aid:
            continue
        groups[aid].append(result)
        if aid not in artifacts:
            artifact = get_artifact(aid)
            if artifact:
                artifacts[aid] = artifact
    if not groups:
        return [], None

    def rank(aid: str) -> tuple[int, str]:
        path = (artifacts.get(aid) or {}).get("logical_path", "").lower()
        if "full_run2" in path:
            score = 0
        elif "full_run1" in path:
            score = 1
        elif "smoke" not in path:
            score = 2
        else:
            score = 3
        return score, path

    selected_id = sorted(groups, key=rank)[0]
    return groups[selected_id], artifacts.get(selected_id)


def hardware_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {"available": False, "reason": "NO_IMPORTED_CAMPAIGN"}
    results = list_results_for_import(active["import_id"], result_type="hardware_profile")
    selected, artifact = _preferred_artifact_group(results)
    if not selected:
        return {"available": False, "reason": "NO_HARDWARE_PROFILE", "source": {"import_id": active["import_id"], "campaign": active.get("campaign") or active.get("filename")}}
    result = selected[0]
    value = result.get("value", {})
    raw_gpu = str(value.get("gpu_raw_info") or "").lower()
    gpu_name = value.get("gpu_name")
    if not gpu_name or str(gpu_name).strip().upper() in {"N/A", "NA", "NONE"}:
        gpu_name = "AMD Instinct MI300X (GFX942)" if ("gfx942" in raw_gpu or "m3000100" in raw_gpu) else "GPU detectada en la campaña"
    backend = value.get("gpu_backend") or value.get("backend")
    hw = {
        "cpu": value.get("cpu_name") or value.get("cpu"),
        "cores": _int(value.get("cpu_cores") or value.get("cores")),
        "ram_gb": _float(value.get("ram_gb") or value.get("ram")),
        "gpu": gpu_name,
        "vram_gb": _float(value.get("vram_gb") or value.get("vram")),
        "backend": str(backend).upper() if backend else None,
        "devices": _int(value.get("gpu_device_count") or value.get("devices")),
        "rocm": value.get("rocm_version") or value.get("rocm"),
        "pytorch": value.get("pytorch_version") or value.get("pytorch"),
        "hip": value.get("torch_hip_version") or value.get("hip"),
        "git_commit": value.get("git_commit"),
        "collected_at": value.get("collected_at"),
        "hostname": value.get("hostname"),
        "platform": value.get("platform"),
        "platform_release": value.get("platform_release"),
        "gpu_available": bool(value.get("torch_cuda_available", True)),
    }
    return {
        "available": True,
        "hardware": hw,
        "result_id": result.get("result_id"),
        "evidence_class": result.get("evidence_class"),
        "source": _source_meta(result, active),
    }


def gpu_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {"available": False, "reason": "NO_IMPORTED_CAMPAIGN", "run1": [], "run2": []}
    results = list_results_for_import(active["import_id"], result_type="gpu_surrogate_baseline")
    if not results:
        return {"available": False, "reason": "NO_GPU_EVIDENCE", "run1": [], "run2": [], "source": {"import_id": active["import_id"], "campaign": active.get("campaign") or active.get("filename")}}

    groups: dict[str, list[dict]] = defaultdict(list)
    artifacts: dict[str, dict] = {}
    for result in results:
        aid = result.get("source_artifact_id")
        if not aid:
            continue
        groups[aid].append(result)
        if aid not in artifacts:
            artifact = get_artifact(aid)
            if artifact:
                artifacts[aid] = artifact

    def rank(aid: str) -> tuple[int, str]:
        path = (artifacts.get(aid) or {}).get("logical_path", "").lower()
        if "full_run1" in path:
            score = 0
        elif "full_run2" in path:
            score = 1
        elif "smoke" not in path:
            score = 2
        else:
            score = 3
        return score, path

    selected_ids = sorted(groups, key=rank)
    full_ids = [aid for aid in selected_ids if "smoke" not in (artifacts.get(aid) or {}).get("logical_path", "").lower()]
    selected_ids = (full_ids or selected_ids)[:2]

    def rows(aid: str) -> list[dict]:
        out = []
        for result in groups.get(aid, []):
            value = result.get("value", {})
            params = result.get("parameters", {})
            out.append({
                "result_id": result.get("result_id"),
                "batch": _int(params.get("batch_size") or value.get("batch_size"), 0),
                "mean": _float(value.get("mean_throughput_ops_sec"), 0.0),
                "peak": _float(value.get("peak_throughput_ops_sec"), 0.0),
                "mem_mb": _float(value.get("memory_mb"), 0.0),
            })
        return sorted(out, key=lambda r: r["batch"])

    run1_id = selected_ids[0] if selected_ids else None
    run2_id = selected_ids[1] if len(selected_ids) > 1 else None
    sources = []
    for aid in selected_ids:
        artifact = artifacts.get(aid)
        if artifact:
            sources.append({
                "artifact_id": aid,
                "logical_path": artifact.get("logical_path"),
                "sha256": artifact.get("sha256"),
                "import_id": artifact.get("import_id"),
            })
    return {
        "available": bool(run1_id),
        "run1": rows(run1_id) if run1_id else [],
        "run2": rows(run2_id) if run2_id else [],
        "label": "SURROGATE",
        "sources": sources,
        "source": {
            "import_id": active["import_id"],
            "campaign": active.get("campaign") or active.get("filename"),
            "filename": active.get("filename"),
            "imported_at": active.get("imported_at"),
            "origin_status": active.get("origin_status"),
        },
    }


def hash_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {"available": False, "reason": "NO_IMPORTED_CAMPAIGN", "algorithms": {}}
    results = list_results_for_import(active["import_id"], result_type="hash_baseline")
    selected, artifact = _preferred_artifact_group(results)
    if not selected:
        return {"available": False, "reason": "NO_HASH_EVIDENCE", "algorithms": {}, "source": {"import_id": active["import_id"], "campaign": active.get("campaign") or active.get("filename")}}
    algorithms: dict[str, list[dict]] = defaultdict(list)
    for result in selected:
        value = result.get("value", {})
        params = result.get("parameters", {})
        alg = str(params.get("algorithm") or value.get("algorithm") or "unknown")
        algorithms[alg].append({
            "result_id": result.get("result_id"),
            "batch": _int(params.get("batch_size") or value.get("batch_size"), 0),
            "mean": _float(value.get("mean_throughput_ops_sec"), 0.0),
            "peak": _float(value.get("peak_throughput_ops_sec"), 0.0),
            "mean_ms": _float(value.get("mean_ms"), 0.0),
        })
    for rows in algorithms.values():
        rows.sort(key=lambda r: r["batch"])
    result = selected[0]
    return {
        "available": True,
        "algorithms": dict(algorithms),
        "source": _source_meta(result, active),
    }


def merkle_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {"available": False, "reason": "NO_IMPORTED_CAMPAIGN", "algorithms": {}}
    results = list_results_for_import(active["import_id"], result_type="merkle_measured")
    selected, artifact = _preferred_artifact_group(results)
    if not selected:
        return {"available": False, "reason": "NO_MERKLE_EVIDENCE", "algorithms": {}, "source": {"import_id": active["import_id"], "campaign": active.get("campaign") or active.get("filename")}}
    algorithms: dict[str, list[dict]] = defaultdict(list)
    for result in selected:
        value = result.get("value", {})
        params = result.get("parameters", {})
        alg = str(params.get("algorithm") or value.get("algorithm") or "unknown")
        algorithms[alg].append({
            "result_id": result.get("result_id"),
            "leaves": _int(params.get("leaf_count") or value.get("leaf_count"), 0),
            "depth": _int(value.get("tree_depth"), 0),
            "total": _int(value.get("total_hash_ops"), 0),
            "mean_ms": _float(value.get("mean_ms"), 0.0),
            "naive_ms": _float(value.get("naive_predicted_ms"), 0.0),
            "corr_ms": _float(value.get("corrected_predicted_ms"), 0.0),
            "naive_err": _float(value.get("naive_error_pct"), 0.0),
            "corr_err": _float(value.get("corrected_error_pct"), 0.0),
            "overhead": _float(value.get("residual_overhead_factor"), 1.0),
        })
    for rows in algorithms.values():
        rows.sort(key=lambda r: r["leaves"])
    return {
        "available": True,
        "algorithms": dict(algorithms),
        "source": _source_meta(selected[0], active),
    }


def pow_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {"available": False, "reason": "NO_IMPORTED_CAMPAIGN", "rows": []}
    results = list_results_for_import(active["import_id"], result_type="pow_measured")
    selected, artifact = _preferred_artifact_group(results)
    if not selected:
        return {"available": False, "reason": "NO_POW_EVIDENCE", "rows": [], "source": {"import_id": active["import_id"], "campaign": active.get("campaign") or active.get("filename")}}
    rows = []
    for result in selected:
        value = result.get("value", {})
        params = result.get("parameters", {})
        rows.append({
            "result_id": result.get("result_id"),
            "difficulty_bits": _int(params.get("difficulty_bits") or value.get("difficulty_bits"), 0),
            "expected_trials": _int(value.get("expected_trials"), 0),
            "actual_trials": _float(value.get("mean_actual_trials"), 0.0),
            "mean_ms": _float(value.get("mean_ms"), 0.0),
            "hash_rate": _float(value.get("mean_hash_rate_ops_sec"), 0.0),
            "predicted_ms": _float(value.get("predicted_ms_expected_trials"), 0.0),
        })
    rows.sort(key=lambda r: r["difficulty_bits"])
    return {"available": True, "rows": rows, "source": _source_meta(selected[0], active)}


def summary_view() -> dict:
    active = latest_completed_import()
    if not active:
        return {
            "available": False,
            "reason": "NO_IMPORTED_CAMPAIGN",
            "hardware": None,
            "gpu_synthetic_peak_run1": None,
            "gpu_synthetic_peak_run2": None,
            "gpu_repeatability_error_pct": None,
            "best_hash_rates": {},
            "source": None,
        }
    hw = hardware_view()
    gpu = gpu_view()
    hashes = hash_view()
    peak1 = max((r.get("peak") or 0 for r in gpu.get("run1", [])), default=None)
    peak2 = max((r.get("peak") or 0 for r in gpu.get("run2", [])), default=None)
    repeatability = None
    if peak1 and peak2:
        repeatability = abs(peak1 - peak2) / ((peak1 + peak2) / 2) * 100
    best_hash_rates = {
        alg: max((r.get("peak") or 0 for r in rows), default=0)
        for alg, rows in hashes.get("algorithms", {}).items()
    }
    return {
        "available": bool(hw.get("available") or gpu.get("available") or hashes.get("available")),
        "hardware": hw.get("hardware") if hw.get("available") else None,
        "gpu_synthetic_peak_run1": peak1,
        "gpu_synthetic_peak_run2": peak2,
        "gpu_repeatability_error_pct": repeatability,
        "best_hash_rates": best_hash_rates,
        "scientific_label": "Carga paralela de bytes clasificada como SUSTITUTO; no equivale a hashing criptográfico nativo en GPU.",
        "source": {
            "import_id": active["import_id"],
            "campaign": active.get("campaign") or active.get("filename"),
            "filename": active.get("filename"),
            "imported_at": active.get("imported_at"),
            "origin_status": active.get("origin_status"),
            "sha256": active.get("sha256"),
            "manifest_sha256": active.get("manifest_sha256"),
        },
    }
