"""Pruebas independientes de la revisión académica. Solo datos locales."""
from pathlib import Path
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from app.main import app, settings
from app.services import evidence_store, ingestion, market_data, report

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "MI300X_Benchmarks.zip"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_store, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(ingestion, "IMPORT_ROOT", tmp_path / "imports")
    monkeypatch.setattr(market_data, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(report, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(settings, "market_data_provider", "offline")
    with TestClient(app) as http:
        yield http


def upload(client, name, data):
    return client.post("/api/imports", files={"file": (name, data)})


@pytest.fixture
def campaign(client):
    response = upload(client, SAMPLE.name, SAMPLE.read_bytes())
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def series(client):
    response = client.get("/api/market/history/VTI?years=5")
    assert response.status_code == 200
    return response.json()["dataset_id"]


def test_empty_baselines(client):
    for view in ("summary", "hardware", "gpu-synthetic", "hash", "merkle", "pow"):
        assert client.get(f"/api/baselines/{view}").json()["available"] is False


def test_campaign(client, campaign):
    assert campaign["status"] == "COMPLETED"
    assert len(campaign["result_ids"]) == 196
    assert campaign["warnings"] == campaign["errors"] == []
    assert campaign["sha256"] == sha256(SAMPLE.read_bytes()).hexdigest()
    assert client.get("/api/baselines/summary").json()["source"]["import_id"] == campaign["import_id"]


def test_bad_zip(client):
    assert upload(client, "campaign.zip", b"invalid archive").status_code == 400
    assert client.get("/api/imports").json()["items"][0]["status"] == "FAILED"


def test_bad_csv(client):
    body = upload(client, "hash_benchmark.csv", b"x,y\n1,2\n").json()
    assert body["status"] == "COMPLETED_WITH_ERRORS"
    assert body["errors"] and not body["result_ids"]


def test_missing(client):
    for path in ("imports/missing", "provenance/artifacts/missing", "provenance/results/missing"):
        assert client.get("/api/" + path).status_code == 404


def test_verify_http(client):
    data = b"PCS: test de integridad"
    artifact = upload(client, "notes.txt", data).json()["artifacts"][0]["artifact_id"]
    path = f"/api/provenance/artifacts/{artifact}"
    detail = client.get(path)
    assert detail.status_code == 200
    verified = client.get(path + "/verify")
    print(f"detalle={detail.status_code} verificacion={verified.status_code}", verified.json())
    assert verified.status_code == 200
    assert verified.json()["match"] is True
    assert verified.json()["sha256_actual"] == sha256(data).hexdigest()
    assert client.get("/api/provenance/artifacts/missing/verify").status_code == 404


def test_cors_allow(client):
    origin = settings.cors_list[0]
    response = client.options("/api/imports", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_deny(client):
    response = client.options("/api/imports", headers={"Origin": "https://other.invalid", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_blockchain_no_data(client):
    assert client.post("/api/blockchain/merkle", json={}).status_code == 400


def test_blockchain_lineage(client, campaign):
    for endpoint, params, category in (
        ("hash-workload", {}, "ESTIMATED"),
        ("merkle", {"model": "corrected"}, "CORRECTED"),
        ("pow", {}, "SIMULATED"),
    ):
        response = client.post(f"/api/blockchain/{endpoint}", json=params)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["evidence_class"] == category
        saved = client.get("/api/provenance/results/" + body["result_id"]).json()
        assert saved["contract"]["valid"] and saved["derived_from"]


def test_market_offline(client, series):
    assert client.get("/api/market/metrics/VTI").json()["dataset_id"] == series
    body = client.get("/api/market/portfolio-metrics?tickers=VTI").json()
    assert body["metrics"][0]["dataset_id"] == series
    assert client.get("/api/market/portfolio-metrics?tickers=").status_code == 400


def scenario(series):
    return {"assets": [{"ticker": "VTI", "weight": 1.0}], "market_dataset_ids": [series],
            "horizon_years": 2, "trials": 500, "seed": 1337}


def test_monte_carlo_replay(client, series):
    path = "/api/portfolio/monte-carlo"
    first = client.post(path, json=scenario(series)).json()
    second = client.post(path, json=scenario(series)).json()
    assert first["derived_from"] == [series]
    assert first["final_value_distribution"] == second["final_value_distribution"]
    assert first["result_id"] == second["result_id"]


def test_context_mismatch(client, series):
    payload = scenario(series)
    payload["assets"][0]["ticker"] = "QQQ"
    assert client.post("/api/portfolio/monte-carlo", json=payload).status_code == 400


def test_rolling_models(client, series):
    payload = {"assets": [{"ticker": "VTI", "weight": 1}], "market_dataset_ids": [series],
               "trials": 500, "years": 5, "rolling_window_months": 24, "forecast_horizon_months": 6}
    response = client.post("/api/portfolio/model-comparison", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation_windows"] > 0 and len(body["summary"]) == 5
    assert body["derived_from"] == [series]
    for row in body["summary"]:
        assert 0 <= row["coverage_rate"] <= 1 and row["average_interval_width"] > 0


def test_pdf_empty(client):
    before = client.get("/api/provenance/summary").json()["results"]
    response = client.post("/api/reports/generate", json={"include_blockchain": False})
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert client.get("/api/provenance/summary").json()["results"] == before


def test_pdf_existing(client, series):
    result = client.post("/api/portfolio/monte-carlo", json=scenario(series)).json()
    before = client.get("/api/provenance/summary").json()["results"]
    response = client.post("/api/reports/generate", json={"monte_carlo_result_id": result["result_id"]})
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")
    assert client.get("/api/provenance/summary").json()["results"] == before
