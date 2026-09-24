"""Background task service using RQ (Redis Queue)."""
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    """Service for managing background tasks via RQ."""

    def __init__(self):
        self._queue = None
        self._enabled = False
        self._try_connect()

    def _try_connect(self):
        """Try to connect to Redis Queue."""
        try:
            from redis import Redis
            from rq import Queue
            import redis as redis_lib

            redis_url = "redis://localhost:6379/1"  # Separate DB for RQ
            redis_client = redis_lib.from_url(redis_url, decode_responses=True)
            redis_client.ping()
            self._queue = Queue("default", connection=redis_client)
            self._enabled = True
            logger.info("RQ background task queue connected")
        except Exception as e:
            logger.warning("RQ not available, background tasks disabled: %s", e)
            self._enabled = False
            self._queue = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enqueue(self, func, *args, **kwargs) -> Optional[Any]:
        """Enqueue a function to run in background."""
        if not self._enabled:
            logger.warning("Background task queue not available, running synchronously")
            # Fallback: run synchronously
            return func(*args, **kwargs)
        try:
            job = self._queue.enqueue(func, *args, **kwargs, job_timeout=300)
            logger.info("Task enqueued: %s (job_id=%s)", func.__name__, job.id)
            return job.id
        except Exception as e:
            logger.error("Failed to enqueue task %s: %s", func.__name__, e)
            # Fallback: run synchronously
            return func(*args, **kwargs)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a background job."""
        if not self._enabled:
            return None
        try:
            from rq import Job
            job = Job.fetch(job_id, connection=self._queue.connection)
            return {
                "id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                "result": job.result if job.is_finished else None,
                "exc_info": job.exc_info if job.is_failed else None,
            }
        except Exception as e:
            logger.debug("Failed to get job status: %s", e)
            return None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self._enabled:
            return {"tasks": "disabled"}
        try:
            return {
                "tasks": "enabled",
                "queued": self._queue.count,
                "started": len(self._queue.started_job_registry),
                "finished": len(self._queue.finished_job_registry),
                "failed": len(self._queue.failed_job_registry),
            }
        except Exception as e:
            logger.debug("Failed to get queue stats: %s", e)
            return {"tasks": "error", "detail": str(e)}

    def health_check(self) -> dict:
        """Check RQ connectivity."""
        if not self._enabled:
            return {"tasks": "disabled", "detail": "RQ not available"}
        try:
            stats = self.get_queue_stats()
            stats["tasks"] = "connected"
            return stats
        except Exception as e:
            return {"tasks": "error", "detail": str(e)}


# Singleton instance
bg_task_service = BackgroundTaskService()
