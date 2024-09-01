import datetime
import multiprocessing
import threading
import time
import logging
import logging.handlers

from sqlalchemy import select, insert, delete
from sqlalchemy.exc import IntegrityError
from pydantic import AnyHttpUrl

from .models import Task, CompletedTask, ProcessLock
from .db import SessionLocal
from .processor import TaskProcessors

from config import RETRY_INTERVAL, FORCE_START_WORKER


def check_or_insert_lock(db, name: str, pid: int) -> tuple[bool, int]:
    try:
        with db.begin():
            # Check if the lock exists
            lock_exists = db.query(ProcessLock).where(ProcessLock.name == name).first()

            if lock_exists:
                logging.getLogger("worker.lock").debug(f"Lock {name} with pid {lock_exists.pid} already exists.")
                return True, lock_exists.pid

            # Insert the lock if it does not exist
            db.execute(
                insert(ProcessLock).values(name=name, pid=pid)
            )
            logging.getLogger("worker.lock").debug(f"Lock {name} with pid {pid} inserted.")
            return False, 0
    except IntegrityError:
        # Handle any integrity errors that may occur
        logging.getLogger("worker.lock").warning(f"DB Integrity error for lock {name} with pid {pid}.")
        db.rollback()
        return True, 0


def release_lock(db: SessionLocal, name: str, pid: int):
    lock = db.query(ProcessLock).where(ProcessLock.name == name).where(ProcessLock.pid == pid).first()
    if lock is not None:
        logging.getLogger("worker.lock").info(f"Releasing lock {name} with pid {pid}.")
        db.delete(lock)
    else:
        logging.getLogger("worker.lock").warning(f"Lock {name} with pid {pid} not found.")
    db.commit()


def is_running():
    return threading.main_thread().is_alive()


def worker():
    db = SessionLocal()
    logger = logging.getLogger(f"worker.executor")

    logger.info("Initializing all processor.")
    processors = {}
    for processor in TaskProcessors.keys():
        cls = TaskProcessors[processor]
        processors[processor] = cls(logger.getChild(cls.__name__), db)

    while is_running():
        db.commit()
        while (task := db.execute(
                select(Task).where((Task.retry_after == None) | (Task.retry_after < datetime.datetime.now())).limit(1)
        ).scalars().first()) is not None and is_running():
            logger.debug(f"Processing task: {task.url}")
            url = AnyHttpUrl(task.url)
            if url.host in TaskProcessors:
                processor = processors[url.host]
                logger.debug(f"Using processor {processor}")
                try:
                    processor.process(task)
                except Exception as e:
                    logger.error(f"Error processing task: {e}, retrying after {RETRY_INTERVAL} seconds...")
                    # Move task to the end of the queue
                    db.delete(task)
                    task.retry_after = datetime.datetime.now() + datetime.timedelta(seconds=RETRY_INTERVAL)
                    db.add(task)
                    db.commit()
                    continue
                db.delete(task)
                db.add(CompletedTask(url=task.url, original_url=task.original_url))
                db.commit()
            time.sleep(1)
        time.sleep(1)


def worker_guard():
    db = SessionLocal()
    pid = multiprocessing.current_process().pid
    logger = logging.getLogger(f"worker.executor")

    logger.info(f"Worker thread starting on process {pid}...")
    existed, existed_pid = check_or_insert_lock(db, "worker", pid)
    if existed:
        logger.error(f"Worker already exists with pid {existed_pid}. Exiting worker...")
        if FORCE_START_WORKER:
            logger.warning("FORCE_START_WORKER is enabled, forcefully starting worker...")
            logger.warning("THIS IS ONLY FOR TESTING PURPOSES, DO NOT USE IN PRODUCTION.")
        else:
            return

    logger.info("[I AM THE CHOSEN ONE]")

    try:
        while is_running():
            try:
                logger.debug("Starting worker loop...")
                worker()
                break
            except KeyboardInterrupt:
                logger.warning("Keyboard interrupt received, stopping worker...")
                break
            except Exception as e:
                logger.error(f"Error in worker thread: {e}, restarting worker after 1 second...")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        release_lock(db, "worker", pid)


def spawn_worker():
    logging.getLogger("worker.spawner").info("Spawning worker thread...")
    threading.Thread(target=worker_guard, args=()).start()


def terminate_worker():
    global running
    logging.getLogger("worker.spawner").info("Terminating worker thread...")
    running = False
    logging.getLogger("worker.spawner").info("Worker thread terminated.")
