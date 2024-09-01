from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.orm import DeclarativeBase

from config import TIMEZONE


class Base(DeclarativeBase):
    pass


# Task record model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, unique=True)
    original_url = Column(Text)
    create_date = Column(DateTime, default=datetime.now(TIMEZONE))
    retry_after = Column(DateTime, default=None, nullable=True)


class CompletedTask(Base):
    __tablename__ = "completed_tasks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, index=True)
    original_url = Column(Text)
    complete_date = Column(DateTime, default=datetime.now(TIMEZONE))


class ProcessLock(Base):
    __tablename__ = "process_lock"

    pid = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, unique=True)
    acquire_date = Column(DateTime, default=datetime.now(TIMEZONE))


Base.registry.configure()
