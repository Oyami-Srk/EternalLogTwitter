from fastapi import Header, HTTPException

from .db import SessionLocal
from config import ACCESS_TOKEN


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_token(x_token: str = Header(...)):
    if x_token != ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="X-Token header invalid")
