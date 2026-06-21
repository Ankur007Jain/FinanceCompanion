import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import StockAnalysis
from schemas import NightlyJobRequest, IngestAnalysisRequest
from services.nightly_runner import run_nightly_analysis

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/nightly")
async def trigger_nightly(body: NightlyJobRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if body.secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")

    async def _run():
        session = SessionLocal()
        try:
            result = await run_nightly_analysis(session, body.tickers)
            return result
        finally:
            session.close()

    background_tasks.add_task(_run)
    return {"status": "started", "tickers": body.tickers or "all"}


@router.post("/ingest-analysis")
def ingest_analysis(body: IngestAnalysisRequest, x_job_secret: str = "", db: Session = Depends(get_db)):
    """Called by the GitHub Actions nightly agent to persist analysis results."""
    if x_job_secret != os.getenv("JOB_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid job secret.")

    existing = db.query(StockAnalysis).filter(
        StockAnalysis.ticker == body.ticker,
        StockAnalysis.analysis_date == body.analysis_date,
    ).first()

    if existing:
        for field, value in body.model_dump().items():
            if value is not None:
                setattr(existing, field, value)
        db.commit()
        return {"status": "updated", "ticker": body.ticker}

    analysis = StockAnalysis(**body.model_dump())
    db.add(analysis)
    db.commit()
    return {"status": "created", "ticker": body.ticker}


@router.get("/admin/tickers")
def list_all_tickers(x_admin_secret: str = "", db: Session = Depends(get_db)):
    """Returns all unique tickers across all watchlists — used by the nightly agent."""
    if x_admin_secret != os.getenv("ADMIN_SECRET", ""):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")
    from models import WatchlistItem
    tickers = db.query(WatchlistItem.ticker).distinct().all()
    return {"tickers": [t[0] for t in tickers]}


@router.get("/health")
def health():
    return {"status": "ok"}
