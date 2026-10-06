from fastapi import APIRouter, HTTPException
from app.schemas import HashWorkloadRequest, MerkleRequest, PowRequest
from app.services.blockchain import simulate_hash_workload, simulate_merkle, simulate_pow

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])

@router.post("/hash-workload")
def hash_workload(req: HashWorkloadRequest):
    try:
        return simulate_hash_workload(req.algorithm, req.transactions, req.hashes_per_transaction, req.conservative_band_pct)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/merkle")
def merkle(req: MerkleRequest):
    try:
        return simulate_merkle(req.algorithm, req.transaction_count, req.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/pow")
def pow_sim(req: PowRequest):
    try:
        return simulate_pow(req.difficulty_bits, req.seconds, req.hash_rate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
