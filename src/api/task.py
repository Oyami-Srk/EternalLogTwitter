from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask
from ..dependencies import get_db
from ..utils.url_transformer import URLTransformers
from ..processor import TaskProcessors, TaskProcessor

router = APIRouter()
logger = logging.getLogger("api.task")


class NewTask(BaseModel):
    url: AnyHttpUrl | list[AnyHttpUrl]
    tag: str | None = None


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
async def get_task(task_id: int):
    return {
        "task": f"Task {task_id} retrieved successfully",
        "success": True,
    }

@router.get("/query/task-by-url")
async def query_task_by_url(url: AnyHttpUrl, db: Session = Depends(get_db)):
    original_url = url
    if url.host in URLTransformers:
        url = URLTransformers[url.host].transform(str(url))
    else:
        url = str(url)

    existing = db.query(Task).where(Task.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(CompletedTask).where(
        CompletedTask.url == url).first()  # type: ignore

    if existing is None:  # type: ignore
        return {
            "existed": False,
            "task": None,
            "success": True,
        }

    data = None
    host = AnyHttpUrl(existing.url).host
    if host in TaskProcessors:
        processor = TaskProcessors[host](logger.getChild(TaskProcessors[host].__name__), db)
        data = processor.get_data(existing)

    return {
        "existed": True,
        "task": {
            "id": existing.id,
            "data": data,
        },
        "success": True,
    }
