"""Public, read-only research routes. No mutation or trade schema is exposed."""
from typing import Literal
from enum import IntEnum
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from puriq_market import SourceUnavailable
from puriq_research import ResearchClient

class CandleInterval(IntEnum):
    FIFTEEN_MINUTES = 900
    ONE_HOUR = 3600
    ONE_DAY = 86400


router = APIRouter()
client = ResearchClient()
STATIC = Path(__file__).resolve().parent / "static" / "research"


@router.get("/research", include_in_schema=False)
def research_page():
    return FileResponse(STATIC / "index.html", media_type="text/html")


@router.get("/api/puriq/v1/research")
def research_observation(
    pair: Literal["BTC-USD", "ETH-USD", "SOL-USD"] = "BTC-USD",
    granularity: CandleInterval = Query(default=CandleInterval.ONE_HOUR),
):
    try:
        return client.history(pair, granularity)
    except SourceUnavailable:
        return JSONResponse(status_code=503, content={
            "status": "UNAVAILABLE", "truth_label": "UNAVAILABLE",
            "reason": "The fixed public source did not return valid completed candles.",
            "trading_enabled": False, "capital_transferred": False,
        })


def research_assets() -> dict:
    """Inspect local distribution bytes; does not fetch or imply market readiness."""
    import hashlib
    from tools.vendor_vela import PINS

    missing, invalid = [], []
    for name in ("index.html", "research.css", "research.js"):
        if not (STATIC / name).is_file():
            missing.append("research/" + name)
    for name, digest in PINS.items():
        path = STATIC.parent / "vendor" / "vela" / Path(name).name
        if not path.is_file():
            missing.append("vendor/vela/" + path.name)
        elif path.stat().st_size > 2_000_000 or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            invalid.append("vendor/vela/" + path.name)
    return {"ready": not missing and not invalid, "missing": missing, "invalid": invalid,
            "renderer": "Vela", "version": "0.7.3", "truth_label": "MEASURED",
            "live_source_observation": False, "trading_enabled": False}


@router.get("/api/puriq/v1/research/readiness")
def research_readiness():
    result = research_assets()
    return JSONResponse(status_code=200 if result["ready"] else 503, content=result)
