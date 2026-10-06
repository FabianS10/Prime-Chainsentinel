from fastapi import APIRouter

from app.services.baseline_views import (
    gpu_view,
    hardware_view,
    hash_view,
    merkle_view,
    pow_view,
    summary_view,
)

router = APIRouter(prefix="/api/baselines", tags=["baselines"])


@router.get("/summary")
def get_summary():
    return summary_view()


@router.get("/hardware")
def get_hardware():
    return hardware_view()


@router.get("/gpu-synthetic")
def get_gpu_synthetic():
    return gpu_view()


@router.get("/hash")
def get_hash():
    return hash_view()


@router.get("/merkle")
def get_merkle():
    return merkle_view()


@router.get("/pow")
def get_pow():
    return pow_view()
