import logging
import time

import gallery_dl

from . import TaskProcessor
from ..db import SessionLocal
from ..models import Task, CompletedTask
from config import GALLERY_DL


class LoggerOutput:
    def __init__(self, logger):
        self.logger = logger

    def start(self, path):
        """Print a message indicating the start of a download"""
        self.logger.info("Starting download: %s", path)

    def skip(self, path):
        """Print a message indicating that a download has been skipped"""
        self.logger.info("Skip download: %s", path)

    def success(self, path):
        """Print a message indicating the completion of a download"""
        self.logger.info("Successfully downloaded: %s", path)

    def progress(self, bytes_total, bytes_downloaded, bytes_per_second):
        """Display download progress"""


class GalleryDownloadJob(gallery_dl.job.DownloadJob):
    def __init__(self, url, logger, parent=None):
        super().__init__(url, parent)
        self.log = logger
        self.out = LoggerOutput(logger)
        self.get_logger = self._get_logger

    def _get_logger(self, name):
        return self.log.getChild(name)


class TwitterProcessor(TaskProcessor):
    def __init__(self, logger: logging.Logger, db: SessionLocal):
        super().__init__(logger, db)
        gallery_dl.config.load()
        for key, value in GALLERY_DL.items():
            gallery_dl.config.set((), key, value)

    @staticmethod
    def apply_to() -> list[str]:
        return ["x.com", "twitter.com"]

    def process(self, task: Task):
        self.logger.debug("Processing task %s", task.url)
        try:
            job = GalleryDownloadJob(task.url, self.logger)
            job.run()
        except Exception as e:
            self.logger.error("Error processing task: %s", e)
            raise Exception("Error processing task")
        self.logger.debug("Task processed successfully")
