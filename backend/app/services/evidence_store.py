from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from contextlib import contextmanager
from uuid import uuid4

SCHEMA_VERSION = "1.0.0"
EVIDENCE_CLASSES = {"MEASURED", "SURROGATE", "ESTIMATED", "CORRECTED", "SIMULATED", "EXPERIMENTAL"}
DERIVED_CLASSES = {"ESTIMATED", "CORRECTED", "SIMULATED"}

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = BACKEND_ROOT / "storage"
DB_PATH = Path(os.getenv("PCS_DB_PATH", str(STORAGE_DIR / "evidence.db")))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _decode(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


@contextmanager
def _connect():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS imports (
                import_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                media_type TEXT,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                campaign TEXT,
                status TEXT NOT NULL,
                origin_status TEXT NOT NULL,
                manifest_sha256 TEXT,
                imported_at TEXT NOT NULL,
                report_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS source_artifacts (
                artifact_id TEXT PRIMARY KEY,
                import_id TEXT,
                logical_path TEXT NOT NULL,
                stored_path TEXT,
                media_type TEXT,
                size_bytes INTEGER,
                sha256 TEXT NOT NULL,
                source_type TEXT NOT NULL,
                evidence_class TEXT,
                validation_status TEXT NOT NULL,
                origin_status TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(import_id) REFERENCES imports(import_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS results (
                result_id TEXT PRIMARY KEY,
                source_artifact_id TEXT,
                schema_version TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                result_type TEXT NOT NULL,
                metric TEXT,
                unit TEXT,
                value_json TEXT NOT NULL DEFAULT '{}',
                parameters_json TEXT NOT NULL DEFAULT '{}',
                environment_json TEXT NOT NULL DEFAULT '{}',
                validity_domain_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_artifact_id) REFERENCES source_artifacts(artifact_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS derivations (
                child_result_id TEXT NOT NULL,
                parent_result_id TEXT NOT NULL,
                transformation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(child_result_id, parent_result_id, transformation),
                FOREIGN KEY(child_result_id) REFERENCES results(result_id) ON DELETE CASCADE,
                FOREIGN KEY(parent_result_id) REFERENCES results(result_id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_results_type ON results(result_type);
            CREATE INDEX IF NOT EXISTS idx_results_class ON results(evidence_class);
            CREATE INDEX IF NOT EXISTS idx_artifacts_import ON source_artifacts(import_id);
            CREATE INDEX IF NOT EXISTS idx_derivations_child ON derivations(child_result_id);
            """
        )


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def content_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return sha256(data).hexdigest()


def create_import(
    *,
    filename: str,
    media_type: str | None,
    size_bytes: int,
    digest: str,
    campaign: str | None,
    status: str = "PROCESSING",
    origin_status: str = "RECORDED_AT_INGEST",
) -> str:
    import_id = f"imp_{uuid4().hex[:16]}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO imports(import_id, filename, media_type, size_bytes, sha256, campaign, status, origin_status, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (import_id, filename, media_type, size_bytes, digest, campaign, status, origin_status, _utc_now()),
        )
    return import_id


def update_import(import_id: str, *, status: str, origin_status: str | None = None, manifest_sha256: str | None = None, report: dict | None = None) -> None:
    with _connect() as conn:
        current = conn.execute("SELECT origin_status FROM imports WHERE import_id = ?", (import_id,)).fetchone()
        if not current:
            raise KeyError(f"Unknown import: {import_id}")
        conn.execute(
            """
            UPDATE imports
               SET status = ?, origin_status = ?, manifest_sha256 = COALESCE(?, manifest_sha256), report_json = ?
             WHERE import_id = ?
            """,
            (status, origin_status or current["origin_status"], manifest_sha256, _json(report or {}), import_id),
        )


def upsert_source_artifact(
    *,
    artifact_id: str | None = None,
    import_id: str | None = None,
    logical_path: str,
    stored_path: str | None,
    media_type: str | None,
    size_bytes: int | None,
    digest: str,
    source_type: str,
    evidence_class: str | None,
    validation_status: str,
    origin_status: str,
    metadata: dict | None = None,
) -> str:
    if evidence_class is not None:
        evidence_class = evidence_class.upper()
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"Unsupported evidence class: {evidence_class}")
    artifact_id = artifact_id or f"art_{digest[:20]}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO source_artifacts(
                artifact_id, import_id, logical_path, stored_path, media_type, size_bytes, sha256,
                source_type, evidence_class, validation_status, origin_status, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                import_id = COALESCE(excluded.import_id, source_artifacts.import_id),
                stored_path = COALESCE(excluded.stored_path, source_artifacts.stored_path),
                validation_status = excluded.validation_status,
                origin_status = excluded.origin_status,
                metadata_json = excluded.metadata_json
            """,
            (
                artifact_id, import_id, logical_path, stored_path, media_type, size_bytes, digest,
                source_type, evidence_class, validation_status, origin_status, _json(metadata or {}), _utc_now(),
            ),
        )
    return artifact_id


def _parent_exists(conn: sqlite3.Connection, result_id: str) -> bool:
    return conn.execute("SELECT 1 FROM results WHERE result_id = ?", (result_id,)).fetchone() is not None


def validate_contract(
    *,
    evidence_class: str,
    source_artifact_id: str | None,
    derived_from: Iterable[str],
    validity_domain: dict | None,
) -> list[str]:
    errors: list[str] = []
    cls = evidence_class.upper()
    parents = list(derived_from)
    if cls not in EVIDENCE_CLASSES:
        errors.append(f"Unknown evidence class: {cls}")
    if cls in {"MEASURED", "SURROGATE"} and not source_artifact_id:
        errors.append(f"{cls} evidence must reference a source artifact")
    if cls in DERIVED_CLASSES and not parents:
        errors.append(f"{cls} evidence must include at least one derived_from result")
    if not isinstance(validity_domain, dict) or not validity_domain:
        errors.append("A non-empty validity_domain is required")
    if cls == "SURROGATE":
        domain = validity_domain or {}
        if not domain.get("represents"):
            errors.append("SURROGATE evidence must state what the workload represents")
        if not domain.get("not_equivalent_to"):
            errors.append("SURROGATE evidence must state what it is not equivalent to")
    return errors


def create_result(
    *,
    result_id: str | None = None,
    source_artifact_id: str | None,
    evidence_class: str,
    result_type: str,
    metric: str | None = None,
    unit: str | None = None,
    value: dict | list | float | int | str | None = None,
    parameters: dict | None = None,
    environment: dict | None = None,
    validity_domain: dict | None = None,
    derived_from: Iterable[str] = (),
    transformation: str = "derived",
    notes: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    replace: bool = False,
) -> str:
    cls = evidence_class.upper()
    parents = list(dict.fromkeys(derived_from))
    errors = validate_contract(
        evidence_class=cls,
        source_artifact_id=source_artifact_id,
        derived_from=parents,
        validity_domain=validity_domain,
    )
    if errors:
        raise ValueError("; ".join(errors))

    result_id = result_id or f"pcs:{result_type}:{uuid4().hex[:20]}"
    with _connect() as conn:
        for parent in parents:
            if not _parent_exists(conn, parent):
                raise ValueError(f"derived_from references an unknown result: {parent}")
        statement = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        conn.execute(
            f"""
            {statement} INTO results(
                result_id, source_artifact_id, schema_version, evidence_class, result_type,
                metric, unit, value_json, parameters_json, environment_json,
                validity_domain_json, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id, source_artifact_id, schema_version, cls, result_type,
                metric, unit, _json(value if value is not None else {}), _json(parameters or {}),
                _json(environment or {}), _json(validity_domain or {}), notes, _utc_now(),
            ),
        )
        if conn.execute("SELECT 1 FROM results WHERE result_id = ?", (result_id,)).fetchone():
            for parent in parents:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO derivations(child_result_id, parent_result_id, transformation, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (result_id, parent, transformation, _utc_now()),
                )
    return result_id


def _row_to_artifact(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    return {
        "artifact_id": row["artifact_id"],
        "import_id": row["import_id"],
        "logical_path": row["logical_path"],
        "stored_path": row["stored_path"],
        "media_type": row["media_type"],
        "size_bytes": row["size_bytes"],
        "sha256": row["sha256"],
        "source_type": row["source_type"],
        "evidence_class": row["evidence_class"],
        "validation_status": row["validation_status"],
        "origin_status": row["origin_status"],
        "metadata": _decode(row["metadata_json"], {}),
        "created_at": row["created_at"],
    }


def _row_to_result(row: sqlite3.Row) -> dict:
    return {
        "result_id": row["result_id"],
        "source_artifact_id": row["source_artifact_id"],
        "schema_version": row["schema_version"],
        "evidence_class": row["evidence_class"],
        "result_type": row["result_type"],
        "metric": row["metric"],
        "unit": row["unit"],
        "value": _decode(row["value_json"], {}),
        "parameters": _decode(row["parameters_json"], {}),
        "environment": _decode(row["environment_json"], {}),
        "validity_domain": _decode(row["validity_domain_json"], {}),
        "notes": row["notes"],
        "created_at": row["created_at"],
    }


def get_result(result_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM results WHERE result_id = ?", (result_id,)).fetchone()
        if not row:
            return None
        result = _row_to_result(row)
        parent_rows = conn.execute(
            """
            SELECT d.parent_result_id, d.transformation, r.evidence_class, r.result_type
              FROM derivations d JOIN results r ON r.result_id = d.parent_result_id
             WHERE d.child_result_id = ?
             ORDER BY d.created_at
            """,
            (result_id,),
        ).fetchall()
        child_rows = conn.execute(
            """
            SELECT d.child_result_id, d.transformation, r.evidence_class, r.result_type
              FROM derivations d JOIN results r ON r.result_id = d.child_result_id
             WHERE d.parent_result_id = ?
             ORDER BY d.created_at
            """,
            (result_id,),
        ).fetchall()
        artifact = None
        if row["source_artifact_id"]:
            artifact = _row_to_artifact(conn.execute("SELECT * FROM source_artifacts WHERE artifact_id = ?", (row["source_artifact_id"],)).fetchone())
        result["derived_from"] = [dict(r) for r in parent_rows]
        result["derived_children"] = [dict(r) for r in child_rows]
        result["source_artifact"] = artifact
        result["contract"] = {
            "valid": not validate_contract(
                evidence_class=result["evidence_class"],
                source_artifact_id=result["source_artifact_id"],
                derived_from=[r["parent_result_id"] for r in parent_rows],
                validity_domain=result["validity_domain"],
            )
        }
        return result


def list_results(limit: int = 100, evidence_class: str | None = None, result_type: str | None = None) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if evidence_class:
        clauses.append("evidence_class = ?")
        params.append(evidence_class.upper())
    if result_type:
        clauses.append("result_type = ?")
        params.append(result_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 1000)))
    with _connect() as conn:
        rows = conn.execute(f"SELECT * FROM results {where} ORDER BY created_at DESC LIMIT ?", params).fetchall()
    return [_row_to_result(r) for r in rows]


def list_imports(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM imports ORDER BY imported_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
    return [
        {
            "import_id": r["import_id"], "filename": r["filename"], "media_type": r["media_type"],
            "size_bytes": r["size_bytes"], "sha256": r["sha256"], "campaign": r["campaign"],
            "status": r["status"], "origin_status": r["origin_status"], "manifest_sha256": r["manifest_sha256"],
            "imported_at": r["imported_at"], "report": _decode(r["report_json"], {}),
        }
        for r in rows
    ]



def latest_completed_import() -> dict | None:
    """Return the most recent successfully completed user import."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM imports
             WHERE status IN ('COMPLETED', 'COMPLETED_WITH_ERRORS')
             ORDER BY imported_at DESC
             LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "import_id": row["import_id"],
        "filename": row["filename"],
        "media_type": row["media_type"],
        "size_bytes": row["size_bytes"],
        "sha256": row["sha256"],
        "campaign": row["campaign"],
        "status": row["status"],
        "origin_status": row["origin_status"],
        "manifest_sha256": row["manifest_sha256"],
        "imported_at": row["imported_at"],
        "report": _decode(row["report_json"], {}),
    }


def list_results_for_import(import_id: str, result_type: str | None = None) -> list[dict]:
    """Return source-backed results that belong to one imported package."""
    params: list[Any] = [import_id]
    type_clause = ""
    if result_type:
        type_clause = " AND r.result_type = ?"
        params.append(result_type)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT r.*
              FROM results r
              JOIN source_artifacts a ON a.artifact_id = r.source_artifact_id
             WHERE a.import_id = ? {type_clause}
             ORDER BY r.created_at DESC
            """,
            params,
        ).fetchall()
    return [_row_to_result(row) for row in rows]

def get_import(import_id: str) -> dict | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM imports WHERE import_id = ?", (import_id,)).fetchone()
        if not r:
            return None
        artifacts = conn.execute("SELECT * FROM source_artifacts WHERE import_id = ? ORDER BY logical_path", (import_id,)).fetchall()
    return {
        "import_id": r["import_id"], "filename": r["filename"], "media_type": r["media_type"],
        "size_bytes": r["size_bytes"], "sha256": r["sha256"], "campaign": r["campaign"],
        "status": r["status"], "origin_status": r["origin_status"], "manifest_sha256": r["manifest_sha256"],
        "imported_at": r["imported_at"], "report": _decode(r["report_json"], {}),
        "artifacts": [_row_to_artifact(a) for a in artifacts],
    }


def get_artifact(artifact_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM source_artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return _row_to_artifact(row)


def verify_artifact(artifact_id: str) -> dict:
    artifact = get_artifact(artifact_id)
    if not artifact:
        raise KeyError(artifact_id)
    stored_path = artifact.get("stored_path")
    if not stored_path:
        return {
            "artifact_id": artifact_id,
            "status": "DIGEST_RECORDED",
            "match": None,
            "sha256_expected": artifact["sha256"],
            "sha256_actual": None,
            "explanation": "The source is external or virtual. Its content digest was recorded at acquisition, but no local raw file is available for byte-for-byte re-verification.",
        }
    path = Path(stored_path)
    if not path.exists():
        return {
            "artifact_id": artifact_id,
            "status": "LOCAL_COPY_MISSING",
            "match": False,
            "sha256_expected": artifact["sha256"],
            "sha256_actual": None,
        }
    actual = file_sha256(path)
    return {
        "artifact_id": artifact_id,
        "status": "INTEGRITY_VERIFIED" if actual == artifact["sha256"] else "INTEGRITY_MISMATCH",
        "match": actual == artifact["sha256"],
        "sha256_expected": artifact["sha256"],
        "sha256_actual": actual,
    }


def provenance_summary() -> dict:
    with _connect() as conn:
        classes = {r["evidence_class"]: r["n"] for r in conn.execute("SELECT evidence_class, COUNT(*) n FROM results GROUP BY evidence_class")}
        imports = conn.execute("SELECT COUNT(*) n FROM imports").fetchone()["n"]
        artifacts = conn.execute("SELECT COUNT(*) n FROM source_artifacts").fetchone()["n"]
        results = conn.execute("SELECT COUNT(*) n FROM results").fetchone()["n"]
        derivations = conn.execute("SELECT COUNT(*) n FROM derivations").fetchone()["n"]
    return {"imports": imports, "artifacts": artifacts, "results": results, "derivations": derivations, "evidence_classes": classes}


def _preferred_import_artifact_results(candidates: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in candidates:
        aid = row.get("source_artifact_id")
        if aid:
            groups.setdefault(aid, []).append(row)
    if not groups:
        return []

    def rank(aid: str) -> tuple[int, str]:
        artifact = get_artifact(aid) or {}
        path = str(artifact.get("logical_path") or "").lower()
        if "full_run2" in path:
            score = 0
        elif "full_run1" in path:
            score = 1
        elif "smoke" not in path:
            score = 2
        else:
            score = 3
        return score, path

    aid = sorted(groups, key=rank)[0]
    return groups[aid]


def best_hash_baseline(algorithm: str) -> tuple[float, str] | None:
    """Use only the most recent imported campaign as a hash baseline source."""
    active = latest_completed_import()
    if not active:
        return None
    candidates = [
        r for r in list_results_for_import(active["import_id"], result_type="hash_baseline")
        if r.get("parameters", {}).get("algorithm") == algorithm
    ]
    candidates = _preferred_import_artifact_results(candidates)
    scored: list[tuple[float, str]] = []
    for row in candidates:
        value = row.get("value", {})
        peak = value.get("peak_throughput_ops_sec") or value.get("peak")
        try:
            if peak is not None:
                scored.append((float(peak), row["result_id"]))
        except (TypeError, ValueError):
            continue
    return max(scored, default=None, key=lambda x: x[0])


def nearest_merkle_baseline(algorithm: str, leaves: int) -> tuple[dict, str] | None:
    """Select a measured Merkle antecedent from the most recent imported campaign."""
    active = latest_completed_import()
    if not active:
        return None
    candidates = [
        r for r in list_results_for_import(active["import_id"], result_type="merkle_measured")
        if r.get("parameters", {}).get("algorithm") == algorithm
    ]
    if not candidates:
        return None
    candidates = _preferred_import_artifact_results(candidates)
    row = min(candidates, key=lambda r: abs(int(r.get("parameters", {}).get("leaf_count", leaves)) - leaves))
    return row.get("value", {}), row["result_id"]


def nearest_pow_baseline(difficulty_bits: int) -> tuple[dict, str] | None:
    """Select the nearest measured PoW row from the most recent imported campaign."""
    active = latest_completed_import()
    if not active:
        return None
    candidates = list_results_for_import(active["import_id"], result_type="pow_measured")
    if not candidates:
        return None
    candidates = _preferred_import_artifact_results(candidates)
    row = min(candidates, key=lambda r: abs(int(r.get("parameters", {}).get("difficulty_bits", difficulty_bits)) - difficulty_bits))
    return row.get("value", {}), row["result_id"]
