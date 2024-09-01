from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from sqlalchemy.orm import Session

from ..models import Task, CompletedTask
from ..dependencies import get_db
from ..utils.url_transformer import URLTransformers

router = APIRouter()


class NewTask(BaseModel):
    url: AnyHttpUrl


@router.post("/task")
async def create_new_task(task: NewTask, db: Session = Depends(get_db)):
    url = ""
    if task.url.host in URLTransformers:
        url = URLTransformers[task.url.host].transform(str(task.url))
    else:
        url = str(task.url)

    existing = db.query(Task).where(Task.url == url).first()  # type: ignore
    existing = existing if existing is not None else db.query(CompletedTask).where(
        CompletedTask.url == url).first()  # type: ignore

    if existing is not None:  # type: ignore
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": "Task already exists",
            "task": {
                "id": existing.id,
                "url": url,
                "type": "completed" if isinstance(existing, CompletedTask) else "pending"
            }
        })

    db.add(Task(url=url, original_url=str(task.url)))
    db.commit()

    return {
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
