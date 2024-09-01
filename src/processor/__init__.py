import logging
from abc import ABC, abstractmethod

from ..db import SessionLocal
from ..models import Task


class TaskProcessor(ABC):
    def __init__(self, logger: logging.Logger, db: SessionLocal):
        self.logger = logger
        self.db = db

    @staticmethod
    @abstractmethod
    def apply_to() -> list[str]:
        pass

    @abstractmethod
    def process(self, task: Task):
        pass

    def __str__(self) -> str:
        return f"[Processor for {','.join(self.apply_to())}]"


from .twitter import TwitterProcessor

TaskProcessors: dict[str, TaskProcessor.__class__] = {}
for processor in [
    TwitterProcessor,
]:
    for host in processor.apply_to():
        TaskProcessors[host] = processor
