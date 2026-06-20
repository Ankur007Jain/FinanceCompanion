import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from schemas import NightlyJobRequest
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


@router.get("/health")
def health():
    return {"status": "ok"}
