"""Opt-in recovery of the original bundled thesis campaign on ephemeral demos.

Never invent benchmark measurements or seed financial observations. Imports use the
same validation, SHA-256 registration and provenance contract as manual uploads.
"""
import logging
import os
from pathlib import Path

from app.services.evidence_store import BACKEND_ROOT, list_imports
from app.services.ingestion import ingest_upload

logger = logging.getLogger(__name__)
BUNDLED_EVIDENCE = BACKEND_ROOT / "demo_seed" / "MI300X_Benchmarks.zip"


def restore_demo_campaign_if_empty() -> None:
    enabled = os.getenv("PCS_DEMO_SEED_SAMPLE", "false").strip().lower() in {"true", "1", "yes"}
    if not enabled or list_imports(limit=1):
        return
    if not BUNDLED_EVIDENCE.is_file():
        raise RuntimeError("Demo evidence restoration is enabled but the original ZIP was not packaged")
    result = ingest_upload(
        filename=BUNDLED_EVIDENCE.name,
        data=BUNDLED_EVIDENCE.read_bytes(),
        media_type="application/zip",
        campaign="BUNDLED_THESIS_DEMO_SAMPLE",
    )
    if result["status"] != "COMPLETED":
        raise RuntimeError(
            f"Bundled campaign could not be fully validated ({result['status']}): {result.get('errors')}"
        )
    logger.warning(
        "Restored thesis demo evidence from bundled original ZIP: import_id=%s sha256=%s",
        result["import_id"], result["sha256"]
    )
