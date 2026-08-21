from typing import Annotated
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask, FailedTask
from ..dependencies import get_db
from ..utils import parse_human_date
from ..utils.url_transformer import URLTransformers
from ..processor import TaskProcessors, TaskProcessor
from config import TIMEZONE

router = APIRouter()
logger = logging.getLogger("api.task")


class NewTask(BaseModel):
    url: AnyHttpUrl | list[AnyHttpUrl]
    tag: str | None = None


def get_task_data(task: Task | CompletedTask, db: Session) -> dict | None:
    host = AnyHttpUrl(task.url).host
    if host in TaskProcessors:
        processor = TaskProcessors[host](logger.getChild(TaskProcessors[host].__name__), db)
        return processor.get_data(task)
    return None


def serialize_task(task: Task | CompletedTask | FailedTask, db: Session | None = None,
                   include_data: bool = False) -> dict:
    base = {
        "id": task.id,
        "url": task.url,
        "original_url": task.original_url,
        "tag": task.tag,
        "create_date": task.create_date.isoformat() if task.create_date else None,
    }
    if isinstance(task, Task):
        base["type"] = "pending"
        base["retry_after"] = task.retry_after.isoformat() if task.retry_after else None
        base["retry_counter"] = task.retry_counter
        base["file_path"] = task.file_path
    elif isinstance(task, CompletedTask):
        base["type"] = "completed"
        base["complete_date"] = task.complete_date.isoformat() if task.complete_date else None
        base["checked"] = task.checked
        base["file_path"] = task.file_path
        if include_data and db is not None:
            base["data"] = get_task_data(task, db)
    elif isinstance(task, FailedTask):
        base["type"] = "failed"
        base["reason"] = task.reason
    return base


def parse_time_param(value: str | None, name: str = "time") -> datetime | None:
    if value is None:
        return None
    # Relative human date, e.g. "7d", "1h"
    try:
        return datetime.now(TIMEZONE) - parse_human_date(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"Invalid {name} format: {value} (use ISO datetime or human like '7d')")


async def process_one_url(url: AnyHttpUrl, db: Session, tag: str | None = None) -> tuple[str, Task | CompletedTask | None]:
    original_url = url
    if url.host in URLTransformers:
        url = URLTransformers[url.host].transform(str(url))
    else:
        url = str(url)

    # FailedTask is not used for checking existing tasks, because we want to manually retry failed tasks
    existing = db.query(Task).where(Task.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(CompletedTask).where(
        CompletedTask.url == url).first()  # type: ignore

    if existing is not None:  # type: ignore
        # Update the tag of an existing completed task when a new tag is provided
        if isinstance(existing, CompletedTask) and tag is not None and existing.tag != tag:
            existing.tag = tag
            db.commit()
        return url, existing

    db.add(Task(url=url, original_url=str(original_url), tag=tag))
    db.commit()

    return url, None


@router.post("/task")
async def create_new_task(task: NewTask, db: Session = Depends(get_db)):
    if isinstance(task.url, list):
        existed = []
        new = []
        for url in task.url:
            url, existing = await process_one_url(url, db, task.tag)
            if existing is not None:
                existed.append({
                    "id": existing.id,
                    "url": url,
                    "type": "completed" if isinstance(existing, CompletedTask) else "pending"
                })
            else:
                new.append(url)
        return {
            "status": "ok",
            "success": True,
            "message": "Batch task created successfully",
            "tasks": {
                "new": new,
                "existed": {
                    int(e['id']): {
                        "type": e['type'],
                        "url": e['url']
                    } for e in existed
                }
            }
        }
    else:
        url, existing = await process_one_url(task.url, db, task.tag)
        if existing is not None:
            return {
                "status": "ok",
                "success": False,
                "message": "Task already exists",
                "task": {
                    "id": existing.id,
                    "url": url,
                    "type": "completed" if isinstance(existing, CompletedTask) else "pending"
                }
            }
        else:
            return {
                "status": "ok",
                "success": True,
                "message": "Task created successfully",
                "task": {
                    "url": url,
                }
            }


@router.get("/task/{task_id}")
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).where(Task.id == task_id).first()  # type: ignore
    task = task if task is not None else db.query(CompletedTask).where(
        CompletedTask.id == task_id).first()  # type: ignore
    task = task if task is not None else db.query(FailedTask).where(
        FailedTask.id == task_id).first()  # type: ignore

    if task is None:  # type: ignore
        raise HTTPException(404, f"Task {task_id} not found")

    return {
        "status": "ok",
        "success": True,
        "task": serialize_task(task, db=db, include_data=isinstance(task, CompletedTask)),
    }

@router.get("/query/task-by-url")
async def query_task_by_url(url: AnyHttpUrl, db: Session = Depends(get_db)):
    original_url = url
    if url.host in URLTransformers:
        url = URLTransformers[url.host].transform(str(url))
    else:
        url = str(url)

    # Search in order: pending -> completed -> failed
    existing = db.query(Task).where(Task.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(CompletedTask).where(
        CompletedTask.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(FailedTask).where(
        FailedTask.url == url).first()  # type: ignore

    if existing is None:  # type: ignore
        return {
            "existed": False,
            "task": None,
            "success": True,
        }

    return {
        "existed": True,
        "success": True,
        "task": serialize_task(existing, db=db, include_data=isinstance(existing, CompletedTask)),
    }


@router.get("/query/task-by-time-range")
async def query_task_by_time_range(start: str | None = None,
                                   end: str | None = None,
                                   tag: str | None = None,
                                   db: Session = Depends(get_db)):
    start_t = parse_time_param(start, "start")
    end_t = parse_time_param(end, "end")

    q = db.query(Task)
    if start_t is not None:
        q = q.where(Task.create_date >= start_t)
    if end_t is not None:
        q = q.where(Task.create_date <= end_t)
    if tag is not None:
        q = q.where(Task.tag == tag)
    pending = [serialize_task(t) for t in q.all()]

    cq = db.query(CompletedTask)
    if start_t is not None:
        cq = cq.where(CompletedTask.complete_date >= start_t)
    if end_t is not None:
        cq = cq.where(CompletedTask.complete_date <= end_t)
    if tag is not None:
        cq = cq.where(CompletedTask.tag == tag)
    completed = [serialize_task(t) for t in cq.all()]

    fq = db.query(FailedTask)
    if start_t is not None:
        fq = fq.where(FailedTask.create_date >= start_t)
    if end_t is not None:
        fq = fq.where(FailedTask.create_date <= end_t)
    if tag is not None:
        fq = fq.where(FailedTask.tag == tag)
    failed = [serialize_task(t) for t in fq.all()]

    return {
        "status": "ok",
        "success": True,
        "start": start,
        "end": end,
        "tag": tag,
        "tasks": pending,
        "completed_tasks": completed,
        "failed_tasks": failed,
    }
