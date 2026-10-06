from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class HashWorkloadRequest(BaseModel):
    algorithm: str = Field(default="sha256")
    transactions: int = Field(default=1_000_000, ge=1)
    hashes_per_transaction: int = Field(default=1, ge=1)
    conservative_band_pct: float = Field(default=15.0, ge=0, le=90)


class MerkleRequest(BaseModel):
    algorithm: str = Field(default="sha256")
    transaction_count: int = Field(default=100_000, ge=2)
    model: str = Field(default="overhead_adjusted")


class PowRequest(BaseModel):
    difficulty_bits: int = Field(default=20, ge=1, le=40)
    hash_rate: float | None = Field(default=None, gt=0)
    seconds: float = Field(default=1.0, gt=0)


class AssetInput(BaseModel):
    ticker: str
    weight: float = Field(ge=0)
    expected_return: float | None = None
    volatility: float | None = None


class PortfolioRequest(BaseModel):
    assets: list[AssetInput]
    market_years: int = Field(default=5, ge=2, le=30)
    market_dataset_ids: list[str] = Field(default_factory=list)
    initial_capital: float = Field(default=1000, ge=0)
    monthly_contribution: float = Field(default=100, ge=0)
    horizon_years: int = Field(default=20, ge=1, le=60)
    trials: int = Field(default=5000, ge=100, le=100_000)
    target_value: float | None = Field(default=None, ge=0)
    # La semilla se conserva como metadato técnico de reproducibilidad.
    # No se presenta como parámetro de negocio en la interfaz principal.
    seed: int = 1337
    use_student_t: bool = False


class ModelComparisonRequest(BaseModel):
    assets: list[AssetInput]
    market_dataset_ids: list[str] = Field(default_factory=list)
    initial_capital: float = Field(default=1000, ge=0)
    monthly_contribution: float = Field(default=100, ge=0)
    years: int = Field(default=7, ge=2, le=30)
    rolling_window_months: int = Field(default=36, ge=12, le=240)
    forecast_horizon_months: int = Field(default=12, ge=3, le=60)
    trials: int = Field(default=3000, ge=500, le=50000)
    # Se usa únicamente para reproducibilidad de los procedimientos estocásticos.
    seed: int = 1337


class ReportRequest(BaseModel):
    """Contenido ya ejecutado que debe incorporarse al reporte.

    El generador de reportes no ejecuta consultas de mercado, Monte Carlo ni
    comparaciones de modelos. Solo representa resultados que ya existen en la sesión.
    """

    title: str = "Prime ChainSentinel — Reporte de evidencia y procedencia"
    include_blockchain: bool = True
    market_snapshot: dict[str, Any] | None = None
    monte_carlo_result_id: str | None = None
    model_comparison_result_id: str | None = None
    notes: str | None = None
