import logging
import time
import os

import gallery_dl

from . import TaskProcessor
from ..db import SessionLocal
from ..models import Task, CompletedTask
from ..utils.url_transformer.twitter import TwitterURLTransformer
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
        self.base_dir = gallery_dl.extractor.find("http://x.com/i/status/123").config("base-directory")

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

    def check(self, task: Task | CompletedTask) -> bool:
        match = TwitterURLTransformer.PATTERN.match(task.url)
        if match:
            username = match.group(1)
            tweet_id = match.group(2)
            possible_ext = ["jpg", "png", "mp4"]
            check_dir = f"{self.base_dir}/twitter/{username}/{tweet_id}_1."
            for ext in possible_ext:
                if os.path.exists(check_dir + ext):
                    return True
        return False
