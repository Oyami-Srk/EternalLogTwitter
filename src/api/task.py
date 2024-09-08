from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask
from ..dependencies import get_db
from ..utils.url_transformer import URLTransformers

router = APIRouter()


class NewTask(BaseModel):
    url: AnyHttpUrl | list[AnyHttpUrl]


async def process_one_url(url: AnyHttpUrl, db: Session) -> tuple[str, Task | CompletedTask | None]:
    original_url = url
    if url.host in URLTransformers:
        url = URLTransformers[url.host].transform(str(url))
    else:
        url = str(url)

    existing = db.query(Task).where(Task.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(CompletedTask).where(
        CompletedTask.url == url).first()  # type: ignore

    if existing is not None:  # type: ignore
        return url, existing

    db.add(Task(url=url, original_url=str(original_url)))
    db.commit()

    return url, None


@router.post("/task")
async def create_new_task(task: NewTask, db: Session = Depends(get_db)):
    if isinstance(task.url, list):
        existed = []
        new = []
        for url in task.url:
            url, existing = await process_one_url(url, db)
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
        url, existing = await process_one_url(task.url, db)
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
