from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask
from ..utils import parse_human_date
from ..dependencies import get_db

from config import TIMEZONE

router = APIRouter()
logger = logging.getLogger("api.status")

@router.get("/status")
async def get_status():
    return {
        "status": "ok",
        "server_time": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/stat")
async def get_count(by: str = "time", with_in: str | None = None, since: int | None = None,
                    db: Session = Depends(get_db)):
    stats = []

    if by == "time":
        if with_in is None and since is None:
            since = 0
        t = None
        if with_in is not None:
            t = datetime.now(TIMEZONE) - parse_human_date(with_in)
        elif since is not None:
            t = datetime.fromtimestamp(since, TIMEZONE)
        logger.info(f"Getting count of tasks since {t}")
        stats.append({
            "type": "time",
            "task": Task.count_since(db, t),
            "completed_task": CompletedTask.count_since(db, t)
        })

    return {
        "status": "ok",
        "stats": stats
    }
