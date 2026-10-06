from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

from app.services.evidence_store import (
    BACKEND_ROOT,
    content_sha256,
    create_import,
    create_result,
    file_sha256,
    update_import,
    upsert_source_artifact,
)

IMPORT_ROOT = BACKEND_ROOT / "storage" / "imports"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 200
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json", ".csv", ".txt"}

RECOGNIZED = {
    "hardware_profile.json",
    "benchmark_full.json",
    "summary.json",
    "hash_benchmark.csv",
    "raw_hash_benchmark.csv",
    "gpu_synthetic_benchmark.csv",
    "raw_gpu_synthetic_benchmark.csv",
    "merkle_benchmark.csv",
    "pow_benchmark.csv",
    "rocm_smi.txt",
    "torch_check.txt",
    "manifest.json",
}

PRIORITY = {
    "hardware_profile.json": 10,
    "hash_benchmark.csv": 20,
    "gpu_synthetic_benchmark.csv": 30,
    "merkle_benchmark.csv": 40,
    "pow_benchmark.csv": 50,
    "raw_hash_benchmark.csv": 60,
    "raw_gpu_synthetic_benchmark.csv": 70,
    "summary.json": 80,
    "benchmark_full.json": 90,
    "rocm_smi.txt": 100,
    "torch_check.txt": 110,
    "manifest.json": 120,
}

REQUIRED_COLUMNS = {
    "hash_benchmark.csv": {"algorithm", "effective_algorithm", "batch_size", "device", "backend", "is_surrogate", "peak_throughput_ops_sec"},
    "raw_hash_benchmark.csv": {"algorithm", "batch_size", "run_index", "time_ms", "throughput_ops_sec"},
    "gpu_synthetic_benchmark.csv": {"algorithm", "effective_algorithm", "batch_size", "device", "backend", "is_surrogate", "peak_throughput_ops_sec"},
    "raw_gpu_synthetic_benchmark.csv": {"algorithm", "batch_size", "run_index", "time_ms", "throughput_ops_sec"},
    "merkle_benchmark.csv": {"algorithm", "leaf_count", "mean_ms", "naive_predicted_ms", "corrected_predicted_ms", "residual_overhead_factor"},
    "pow_benchmark.csv": {"difficulty_bits", "mean_ms", "mean_hash_rate_ops_sec"},
}

REQUIRED_JSON_KEYS = {
    "hardware_profile.json": {"collected_at", "cpu_name", "gpu_backend", "git_commit"},
    "benchmark_full.json": {"meta", "hardware"},
    "summary.json": {"generated_at"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _safe_zip_member(info: zipfile.ZipInfo) -> tuple[bool, str | None]:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts:
        return False, "unsafe path"
    # Unix symlink flag in external attributes.
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        return False, "symbolic link"
    if info.file_size > MAX_MEMBER_BYTES:
        return False, "member too large"
    if info.is_dir():
        return True, None
    if Path(info.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        return False, "unsupported file extension"
    return True, None


def _extract_zip_safely(zip_path: Path, raw_dir: Path) -> tuple[list[Path], list[str]]:
    accepted: list[Path] = []
    warnings: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError(f"ZIP has {len(infos)} entries; limit is {MAX_ZIP_ENTRIES}")
        total = sum(i.file_size for i in infos if not i.is_dir())
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"ZIP uncompressed size exceeds {MAX_UNCOMPRESSED_BYTES} bytes")
        for info in infos:
            ok, reason = _safe_zip_member(info)
            if not ok:
                warnings.append(f"Rejected {info.filename}: {reason}")
                continue
            if info.is_dir():
                continue
            destination = raw_dir / PurePosixPath(info.filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            accepted.append(destination)
    return accepted, warnings


def _artifact_class(filename: str) -> str | None:
    name = Path(filename).name
    if name in {"gpu_synthetic_benchmark.csv", "raw_gpu_synthetic_benchmark.csv"}:
        return "SURROGATE"
    if name in {"hash_benchmark.csv", "raw_hash_benchmark.csv", "merkle_benchmark.csv", "pow_benchmark.csv", "hardware_profile.json"}:
        return "MEASURED"
    return None


def _source_type(filename: str) -> str:
    name = Path(filename).name
    if name.endswith(".csv"):
        return "benchmark_csv"
    if name.endswith(".json"):
        return "benchmark_json"
    return "benchmark_text"


def _validate_json(path: Path) -> tuple[bool, dict | list | None, str | None]:
    try:
        return True, json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, None, str(exc)


def _validate_csv(path: Path) -> tuple[bool, list[dict], str | None]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            return False, [], "CSV contains no data rows"
        if not rows[0].keys():
            return False, [], "CSV has no header"
        return True, rows, None
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return False, [], str(exc)



def _validate_recognized_schema(filename: str, parsed: dict | list | None, rows: list[dict]) -> list[str]:
    errors: list[str] = []
    if filename in REQUIRED_COLUMNS:
        columns = set(rows[0].keys()) if rows else set()
        missing = sorted(REQUIRED_COLUMNS[filename] - columns)
        if missing:
            errors.append(f"missing required columns: {', '.join(missing)}")
    if filename in REQUIRED_JSON_KEYS:
        if not isinstance(parsed, dict):
            errors.append("expected a JSON object")
        else:
            missing = sorted(REQUIRED_JSON_KEYS[filename] - set(parsed.keys()))
            if missing:
                errors.append(f"missing required JSON keys: {', '.join(missing)}")
    return errors

def _register_hash_rows(rows: list[dict], artifact_id: str, artifact_digest: str, environment: dict) -> list[str]:
    result_ids: list[str] = []
    for row in rows:
        alg = (row.get("algorithm") or "unknown").strip()
        effective = (row.get("effective_algorithm") or alg).strip()
        batch = _int(row.get("batch_size")) or 0
        surrogate = _bool(row.get("is_surrogate"))
        cls = "SURROGATE" if surrogate else "MEASURED"
        rid = f"pcs:import:hash:{artifact_digest[:12]}:{alg}:{batch}"
        validity = {
            "device": row.get("device"),
            "backend": row.get("backend"),
            "algorithm": effective,
            "batch_size": batch,
        }
        if surrogate:
            validity.update({
                "represents": "synthetic byte workload",
                "not_equivalent_to": "native cryptographic hashing",
            })
        create_result(
            result_id=rid,
            source_artifact_id=artifact_id,
            evidence_class=cls,
            result_type="hash_baseline" if not surrogate else "gpu_surrogate_baseline",
            metric="peak_throughput_ops_sec",
            unit="ops/s",
            value={**row, "peak_throughput_ops_sec": _float(row.get("peak_throughput_ops_sec"))},
            parameters={"algorithm": alg, "effective_algorithm": effective, "batch_size": batch, "transaction_byte_size": _int(row.get("transaction_byte_size"))},
            environment=environment,
            validity_domain=validity,
            notes=row.get("notes"),
        )
        result_ids.append(rid)
    return result_ids


def _register_gpu_rows(rows: list[dict], artifact_id: str, artifact_digest: str, environment: dict) -> list[str]:
    result_ids: list[str] = []
    for row in rows:
        batch = _int(row.get("batch_size")) or 0
        rid = f"pcs:import:gpu-surrogate:{artifact_digest[:12]}:{batch}"
        create_result(
            result_id=rid,
            source_artifact_id=artifact_id,
            evidence_class="SURROGATE",
            result_type="gpu_surrogate_baseline",
            metric="peak_throughput_ops_sec",
            unit="ops/s",
            value={**row, "peak_throughput_ops_sec": _float(row.get("peak_throughput_ops_sec"))},
            parameters={"batch_size": batch, "transaction_byte_size": _int(row.get("transaction_byte_size")), "workload": row.get("effective_algorithm")},
            environment=environment,
            validity_domain={
                "device": row.get("device"),
                "backend": row.get("backend"),
                "represents": "byte-parallel synthetic workload on GPU",
                "not_equivalent_to": "native SHA-256, SHA3-256 or BLAKE3 GPU hashing",
            },
            notes=row.get("notes"),
        )
        result_ids.append(rid)
    return result_ids


def _best_parent_for_algorithm(created_results: list[str], algorithm: str) -> str | None:
    # Imported hash results encode algorithm in their stable ID.
    candidates = [rid for rid in created_results if rid.startswith("pcs:import:hash:") and f":{algorithm}:" in rid]
    return candidates[0] if candidates else None


def _register_merkle_rows(rows: list[dict], artifact_id: str, artifact_digest: str, environment: dict, created_results: list[str]) -> list[str]:
    result_ids: list[str] = []
    for row in rows:
        alg = (row.get("algorithm") or "unknown").strip()
        leaves = _int(row.get("leaf_count")) or 0
        measured_id = f"pcs:import:merkle:measured:{artifact_digest[:12]}:{alg}:{leaves}"
        create_result(
            result_id=measured_id,
            source_artifact_id=artifact_id,
            evidence_class="MEASURED",
            result_type="merkle_measured",
            metric="mean_ms",
            unit="ms",
            value={**row, "mean_ms": _float(row.get("mean_ms"))},
            parameters={"algorithm": alg, "leaf_count": leaves},
            environment=environment,
            validity_domain={"device": row.get("device", "cpu"), "algorithm": alg, "leaf_count": leaves, "use": "measured Merkle construction"},
            notes=row.get("notes"),
        )
        result_ids.append(measured_id)

        parent = _best_parent_for_algorithm(created_results + result_ids, alg)
        if not parent:
            continue

        naive_id = f"pcs:import:merkle:naive:{artifact_digest[:12]}:{alg}:{leaves}"
        create_result(
            result_id=naive_id,
            source_artifact_id=None,
            evidence_class="ESTIMATED",
            result_type="merkle_estimate",
            metric="naive_predicted_ms",
            unit="ms",
            value={"predicted_ms": _float(row.get("naive_predicted_ms")), "error_pct": _float(row.get("naive_error_pct"))},
            parameters={"algorithm": alg, "leaf_count": leaves, "model": "N-1 internal nodes"},
            environment=environment,
            validity_domain={"algorithm": alg, "leaf_count": leaves, "model": "naive", "extrapolation": "not assumed"},
            derived_from=[parent],
            transformation="Merkle naive N-1 model",
        )
        result_ids.append(naive_id)

        corrected_id = f"pcs:import:merkle:corrected:{artifact_digest[:12]}:{alg}:{leaves}"
        create_result(
            result_id=corrected_id,
            source_artifact_id=None,
            evidence_class="CORRECTED",
            result_type="merkle_corrected",
            metric="corrected_predicted_ms",
            unit="ms",
            value={"predicted_ms": _float(row.get("corrected_predicted_ms")), "error_pct": _float(row.get("corrected_error_pct")), "residual_overhead_factor": _float(row.get("residual_overhead_factor"))},
            parameters={"algorithm": alg, "leaf_count": leaves, "model": "2N-1 structural correction"},
            environment=environment,
            validity_domain={"algorithm": alg, "leaf_count": leaves, "model": "corrected", "extrapolation": "not assumed"},
            derived_from=[parent],
            transformation="Merkle structural 2N-1 correction",
        )
        result_ids.append(corrected_id)
    return result_ids


def _register_pow_rows(rows: list[dict], artifact_id: str, artifact_digest: str, environment: dict) -> list[str]:
    ids: list[str] = []
    for row in rows:
        difficulty = _int(row.get("difficulty_bits")) or 0
        rid = f"pcs:import:pow:{artifact_digest[:12]}:d{difficulty}"
        create_result(
            result_id=rid,
            source_artifact_id=artifact_id,
            evidence_class="MEASURED",
            result_type="pow_measured",
            metric="mean_hash_rate_ops_sec",
            unit="ops/s",
            value=row,
            parameters={"difficulty_bits": difficulty},
            environment=environment,
            validity_domain={"mode": "offline educational toy PoW", "not_equivalent_to": "live cryptocurrency mining"},
            notes=row.get("notes"),
        )
        ids.append(rid)
    return ids


def _verify_declared_manifest(files: list[Path], raw_dir: Path) -> tuple[str, list[str]]:
    manifests = [p for p in files if p.name == "manifest.json"]
    if not manifests:
        return "RECORDED_AT_INGEST", []
    warnings: list[str] = []
    try:
        data = json.loads(manifests[0].read_text(encoding="utf-8"))
        expected = data.get("artifacts", [])
        if not isinstance(expected, list) or not expected:
            return "DECLARED_MANIFEST_INVALID", ["manifest.json contains no artifacts list"]
        lookup = {str(p.relative_to(raw_dir)).replace("\\", "/"): p for p in files}
        all_match = True
        for item in expected:
            rel = str(item.get("path", "")).replace("\\", "/")
            expected_hash = str(item.get("sha256", "")).lower()
            p = lookup.get(rel)
            if not p:
                all_match = False
                warnings.append(f"Manifest artifact missing: {rel}")
                continue
            actual = file_sha256(p)
            if actual != expected_hash:
                all_match = False
                warnings.append(f"Manifest hash mismatch: {rel}")
        return ("MANIFEST_VERIFIED" if all_match else "MANIFEST_MISMATCH"), warnings
    except Exception as exc:
        return "DECLARED_MANIFEST_INVALID", [f"Unable to validate manifest.json: {exc}"]


def ingest_upload(filename: str, data: bytes, media_type: str | None = None, campaign: str | None = None) -> dict:
    if not filename:
        raise ValueError("A filename is required")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Upload exceeds {MAX_UPLOAD_BYTES} bytes")

    extension = Path(filename).suffix.lower()
    if extension not in {".zip", ".json", ".csv", ".txt"}:
        raise ValueError("Supported upload formats are ZIP, JSON, CSV and TXT")

    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)
    upload_digest = content_sha256(data)
    import_id = create_import(
        filename=filename,
        media_type=media_type,
        size_bytes=len(data),
        digest=upload_digest,
        campaign=campaign,
    )
    import_dir = IMPORT_ROOT / import_id
    raw_dir = import_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    original_path = import_dir / f"original{extension}"
    original_path.write_bytes(data)

    warnings: list[str] = []
    errors: list[str] = []
    created_results: list[str] = []
    artifacts: list[dict] = []
    environment: dict = {"campaign": campaign}

    try:
        if extension == ".zip":
            files, zip_warnings = _extract_zip_safely(original_path, raw_dir)
            warnings.extend(zip_warnings)
        else:
            target = raw_dir / Path(filename).name
            target.write_bytes(data)
            files = [target]

        origin_status, manifest_warnings = _verify_declared_manifest(files, raw_dir)
        warnings.extend(manifest_warnings)

        # Register the original package itself so its exact bytes remain auditable.
        package_artifact_id = upsert_source_artifact(
            artifact_id=f"pcs:artifact:package:{import_id}:{upload_digest[:12]}",
            import_id=import_id,
            logical_path=filename,
            stored_path=str(original_path),
            media_type=media_type or "application/octet-stream",
            size_bytes=len(data),
            digest=upload_digest,
            source_type="uploaded_package",
            evidence_class=None,
            validation_status="VALID",
            origin_status=origin_status,
            metadata={"campaign": campaign, "note": "Original upload preserved byte-for-byte."},
        )
        artifacts.append({"artifact_id": package_artifact_id, "path": filename, "sha256": upload_digest, "recognized": True})

        files = sorted(files, key=lambda p: (PRIORITY.get(p.name, 999), str(p)))
        for path in files:
            rel = str(path.relative_to(raw_dir)).replace("\\", "/")
            basename = path.name
            digest = file_sha256(path)
            recognized = basename in RECOGNIZED
            validation_status = "VALID"
            parsed: dict | list | None = None
            rows: list[dict] = []

            if path.suffix.lower() == ".json":
                ok, parsed, err = _validate_json(path)
                if not ok:
                    validation_status = "INVALID"
                    errors.append(f"{rel}: {err}")
            elif path.suffix.lower() == ".csv":
                ok, rows, err = _validate_csv(path)
                if not ok:
                    validation_status = "INVALID"
                    errors.append(f"{rel}: {err}")

            if validation_status == "VALID" and recognized:
                schema_errors = _validate_recognized_schema(basename, parsed, rows)
                if schema_errors:
                    validation_status = "INVALID"
                    errors.extend([f"{rel}: {msg}" for msg in schema_errors])

            cls = _artifact_class(basename)
            artifact_id = upsert_source_artifact(
                artifact_id=f"pcs:artifact:{import_id}:{content_sha256(rel)[:8]}:{digest[:12]}",
                import_id=import_id,
                logical_path=rel,
                stored_path=str(path),
                media_type="application/json" if path.suffix.lower() == ".json" else "text/csv" if path.suffix.lower() == ".csv" else "text/plain",
                size_bytes=path.stat().st_size,
                digest=digest,
                source_type=_source_type(basename),
                evidence_class=cls,
                validation_status=validation_status if recognized else "UNRECOGNIZED",
                origin_status=origin_status,
                metadata={"recognized": recognized, "campaign": campaign, "basename": basename},
            )
            artifacts.append({"artifact_id": artifact_id, "path": rel, "sha256": digest, "recognized": recognized, "validation_status": validation_status})

            if validation_status != "VALID" or not recognized:
                if not recognized:
                    warnings.append(f"Stored but not interpreted: {rel}")
                continue

            if basename == "hardware_profile.json" and isinstance(parsed, dict):
                environment = parsed
                create_result(
                    result_id=f"pcs:import:hardware:{digest[:20]}",
                    source_artifact_id=artifact_id,
                    evidence_class="MEASURED",
                    result_type="hardware_profile",
                    metric=None,
                    unit=None,
                    value=parsed,
                    parameters={"campaign": campaign},
                    environment=parsed,
                    validity_domain={"use": "execution environment metadata", "host": parsed.get("hostname")},
                    notes="Environment profile captured by the benchmark campaign.",
                )
                created_results.append(f"pcs:import:hardware:{digest[:20]}")
            elif basename == "hash_benchmark.csv":
                ids = _register_hash_rows(rows, artifact_id, digest, environment)
                created_results.extend(ids)
            elif basename == "gpu_synthetic_benchmark.csv":
                ids = _register_gpu_rows(rows, artifact_id, digest, environment)
                created_results.extend(ids)
            elif basename == "merkle_benchmark.csv":
                ids = _register_merkle_rows(rows, artifact_id, digest, environment, created_results)
                created_results.extend(ids)
            elif basename == "pow_benchmark.csv":
                ids = _register_pow_rows(rows, artifact_id, digest, environment)
                created_results.extend(ids)

        generated_manifest = {
            "schema_version": "1.0.0",
            "import_id": import_id,
            "generated_at": _utc_now(),
            "original": {"filename": filename, "sha256": upload_digest, "size_bytes": len(data)},
            "origin_assurance": origin_status,
            "artifacts": [{"path": a["path"], "sha256": a["sha256"]} for a in artifacts],
            "statement": "Hashes prove byte-level integrity from the moment of ingestion. They do not by themselves prove that an external source was truthful or that the file was created by a particular actor.",
        }
        manifest_path = import_dir / "generated_manifest.json"
        manifest_path.write_text(json.dumps(generated_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest_digest = file_sha256(manifest_path)

        report = {
            "files_received": len(files),
            "artifacts_registered": len(artifacts),
            "results_registered": len(created_results),
            "warnings": warnings,
            "errors": errors,
            "origin_status": origin_status,
            "generated_manifest": str(manifest_path),
            "integrity_note": "A matching SHA-256 confirms that stored bytes have not changed since ingestion; authenticity of the original producer requires an independently trusted signature or source attestation.",
        }
        status = "COMPLETED" if not errors else "COMPLETED_WITH_ERRORS"
        update_import(import_id, status=status, origin_status=origin_status, manifest_sha256=manifest_digest, report=report)
        return {"import_id": import_id, "status": status, "sha256": upload_digest, "origin_status": origin_status, "manifest_sha256": manifest_digest, "artifacts": artifacts, "result_ids": created_results, "warnings": warnings, "errors": errors}
    except Exception as exc:
        update_import(import_id, status="FAILED", report={"errors": [str(exc)], "warnings": warnings})
        raise
