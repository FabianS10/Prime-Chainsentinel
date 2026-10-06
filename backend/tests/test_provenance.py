from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.services import evidence_store, ingestion
from app.services.blockchain import simulate_merkle
from app.services.market_data import get_history


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        evidence_store.DB_PATH = root / "evidence.db"
        ingestion.IMPORT_ROOT = root / "imports"
        evidence_store.init_database()

    def tearDown(self):
        self.tmp.cleanup()

    def _import_sample_campaign(self):
        project_root = Path(__file__).resolve().parents[2]
        sample_zip = project_root / "sample_data" / "MI300X_Benchmarks.zip"
        self.assertTrue(sample_zip.exists(), f"No se encontró la campaña de prueba: {sample_zip}")
        result = ingestion.ingest_upload(sample_zip.name, sample_zip.read_bytes(), "application/zip", "campaña-prueba")
        self.assertIn(result["status"], {"COMPLETED", "COMPLETED_WITH_ERRORS"})
        return result

    def test_contract_rejects_derived_result_without_lineage(self):
        with self.assertRaises(ValueError):
            evidence_store.create_result(
                source_artifact_id=None,
                evidence_class="ESTIMATED",
                result_type="bad_estimate",
                validity_domain={"use": "test"},
                derived_from=[],
            )

    def test_blockchain_lab_requires_imported_evidence(self):
        with self.assertRaises(ValueError):
            simulate_merkle("sha256", 1024, "corrected")

    def test_merkle_result_has_valid_lineage_after_import(self):
        imported = self._import_sample_campaign()
        self.assertTrue(imported["result_ids"])
        out = simulate_merkle("sha256", 1024, "corrected")
        self.assertEqual(out["evidence_class"], "CORRECTED")
        self.assertTrue(out["derived_from"])
        stored = evidence_store.get_result(out["result_id"])
        self.assertTrue(stored["contract"]["valid"])
        self.assertGreaterEqual(len(stored["derived_from"]), 1)

    def test_csv_ingestion_and_tamper_detection(self):
        csv_data = (
            "algorithm,effective_algorithm,batch_size,transaction_byte_size,device,backend,is_surrogate,mean_ms,median_ms,std_ms,min_ms,max_ms,mean_throughput_ops_sec,median_throughput_ops_sec,peak_throughput_ops_sec,memory_mb,notes\n"
            "sha256,sha256,1000,256,cpu,hashlib,False,0.4,0.4,0.01,0.39,0.42,2200000,2200000,2400000,,test\n"
        ).encode()
        result = ingestion.ingest_upload("hash_benchmark.csv", csv_data, "text/csv", "test")
        self.assertEqual(result["status"], "COMPLETED")
        detail = evidence_store.get_import(result["import_id"])
        file_artifact = next(a for a in detail["artifacts"] if a["logical_path"] == "hash_benchmark.csv")
        verified = evidence_store.verify_artifact(file_artifact["artifact_id"])
        self.assertTrue(verified["match"])
        Path(file_artifact["stored_path"]).write_text("tampered", encoding="utf-8")
        failed = evidence_store.verify_artifact(file_artifact["artifact_id"])
        self.assertFalse(failed["match"])
        self.assertEqual(failed["status"], "INTEGRITY_MISMATCH")

    def test_zip_path_traversal_is_not_extracted(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../evil.csv", "a,b\n1,2\n")
            zf.writestr("summary.json", "{}")
        result = ingestion.ingest_upload("test.zip", buffer.getvalue(), "application/zip", "zip-test")
        self.assertTrue(any("unsafe path" in w for w in result["warnings"]))
        self.assertFalse((Path(self.tmp.name) / "evil.csv").exists())

    def test_offline_market_series_gets_digest_and_provenance(self):
        payload = get_history("VTI", years=2, provider="offline", force_refresh=True)
        self.assertTrue(payload.get("dataset_id"))
        self.assertTrue(payload.get("series_sha256"))
        self.assertEqual(payload.get("evidence_class"), "SIMULATED")
        stored = evidence_store.get_result(payload["dataset_id"])
        self.assertTrue(stored["contract"]["valid"])


if __name__ == "__main__":
    unittest.main()
