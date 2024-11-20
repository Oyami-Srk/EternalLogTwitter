import datetime
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask
from ..dependencies import get_db
from ..utils.url_transformer import URLTransformers
from ..processor import TaskProcessors, TaskProcessor

router = APIRouter()
logger = logging.getLogger("api.check")


async def check_task(processors: dict[str, TaskProcessor], task: Task | CompletedTask, db: Session):
    host = AnyHttpUrl(task.url).host
    if host in TaskProcessors:
        processor = processors[host]
        r = processor.check(task)
        logger.info(f"Checked {task.url} with {processor} returned {r}")
        return r
    logger.info(f"Checking {task.url} failed, no processor found")
    return False


async def check_all(processors: dict[str, TaskProcessor], db: Session):
    partial = False
    total = 0
    ok = 0
    failures = []
    begin_time = datetime.datetime.now()
    for t in db.query(CompletedTask).where(CompletedTask.checked == False).all():  # type: ignore
        total += 1
        checked = await check_task(processors, t, db)
        if checked:
            ok += 1
            t.checked = True
            db.commit()
        else:
            failures.append(t)
        if total % 100 == 0 and datetime.datetime.now() - begin_time > datetime.timedelta(seconds=120):
            partial = True
            break
    return {
        "status": "ok" if not partial else "partial",
        "total": total,
        "ok": ok,
        "elapsed": datetime.datetime.now() - begin_time,
        "failures": [f.url for f in failures]
    }


async def check_by_url(processors: dict[str, TaskProcessor], urls: AnyHttpUrl | list[AnyHttpUrl]):
    raise HTTPException(400, "Not implemented")


async def check_by_time_range(processors: dict[str, TaskProcessor], start: datetime.datetime, end: datetime.datetime):
    raise HTTPException(400, "Not implemented")


@router.post("/check")
async def check(all: Optional[bool] = None,
                by_url: Optional[AnyHttpUrl | list[AnyHttpUrl]] = None,
                by_time_range: Optional[tuple[datetime.datetime, datetime.datetime]] = None,
                db: Session = Depends(get_db)):
    processors = {}
    for processor in TaskProcessors.keys():
        cls = TaskProcessors[processor]
        processors[processor] = cls(logger.getChild(cls.__name__), db)

    if all is not None:
        if all:
            return await check_all(processors, db)
        else:
            return {"status": "ok", "message": "No check performed"}
    elif by_url is not None:
        return await check_by_url(processors, by_url)
    elif by_time_range is not None:
        return await check_by_time_range(processors, *by_time_range)
    else:
        raise HTTPException(400, "Exactly one of all, by_url, by_time_range must be provided")
