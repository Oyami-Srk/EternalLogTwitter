from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, Session

from config import TIMEZONE


def get_local_time():
    return datetime.now(TIMEZONE)


class Base(DeclarativeBase):
    pass


# Task record model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, unique=True)
    original_url = Column(Text)
    create_date = Column(DateTime, default=get_local_time)
    retry_after = Column(DateTime, default=None, nullable=True)

    @classmethod
    def count_since(cls, db: Session, t):
        return db.query(cls).filter(cls.create_date >= t).count()


class CompletedTask(Base):
    __tablename__ = "completed_tasks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text, index=True)
    original_url = Column(Text)
    complete_date = Column(DateTime, default=get_local_time)
    checked = Column(Boolean, default=False, nullable=False)

    @classmethod
    def count_since(cls, db: Session, t):
        return db.query(cls).filter(cls.complete_date >= t).count()


class ProcessLock(Base):
    __tablename__ = "process_lock"

    pid = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, unique=True)
    acquire_date = Column(DateTime, default=get_local_time)


Base.registry.configure()
