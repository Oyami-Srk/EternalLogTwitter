import logging
import time
import os
import base64

import gallery_dl

from . import TaskProcessor
from ..db import SessionLocal
from ..models import Task, CompletedTask
from ..utils.url_transformer.twitter import TwitterURLTransformer
from config import GALLERY_DL


class LoggerOutput:
    def __init__(self, logger):
        self.logger = logger
        self.paths: list[str] = []
        self.skipped_paths: list[str] = []

    def start(self, path):
        """Print a message indicating the start of a download"""
        self.logger.info("Starting download: %s", path)

    def skip(self, path):
        """Print a message indicating that a download has been skipped"""
        self.logger.info("Skip download: %s", path)
        self.skipped_paths.append(path)

    def success(self, path):
        """Print a message indicating the completion of a download"""
        self.logger.info("Successfully downloaded: %s", path)
        self.paths.append(path)

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
            files = []
            for p in job.out.paths:
                files.append({"path": p, "skipped": False})
            for p in job.out.skipped_paths:
                files.append({"path": p, "skipped": True})
            if not files and job.pathfmt is not None and job.pathfmt.path:
                files = [{"path": job.pathfmt.path, "skipped": False}]
            task.file_path = files or None
            self.db.commit()
        except Exception as e:
            self.logger.error("Error processing task: %s", e)
            raise Exception("Error processing task")
        self.logger.debug("Task processed successfully")

    def get_all_files(self, task: Task | CompletedTask) -> list[tuple[str, bool]]:
        """Return all recorded files as (path, skipped) pairs."""
        if not task.file_path:
            return []
        paths = task.file_path if isinstance(task.file_path, list) else [task.file_path]
        result = []
        for item in paths:
            if isinstance(item, dict):
                result.append((item.get("path"), bool(item.get("skipped"))))
            else:
                # legacy plain-string entries
                result.append((item, False))
        return result

    def get_downloaded_files(self, task: Task | CompletedTask) -> list[str]:
        # A skipped file that still exists on disk has been downloaded before,
        # so it counts as downloaded regardless of the skipped flag.
        return [p for p, _ in self.get_all_files(task) if p and os.path.exists(p)]

    def check(self, task: Task | CompletedTask) -> bool:
        if self.get_downloaded_files(task):
            return True
        return False

    def get_data(self, task: Task | CompletedTask) -> dict | None:
        entries = self.get_all_files(task)
        if not entries:
            return None
        files = {}
        for path, skipped in entries:
            if not path:
                continue
            name = os.path.basename(path)
            content = None
            if os.path.exists(path):
                content = base64.b64encode(open(path, "rb").read()).decode("utf-8")
            files[name] = {"skipped": skipped, "content": content}
        return {"files": files}
