"""Health check endpoint with DB and cache verification."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func

from app.database import get_db
from app.models.appointment import Appointment
from app.services.cache import cache_service
from app.services.background_tasks import bg_task_service
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """System health check with DB and cache status.
    
    Returns:
        - status: overall system status ("healthy" or "degraded")
        - database: DB connectivity status
        - cache: Redis cache status (if available)
        - tasks: Background task queue status (if available)
    
    **Example response:**
    ```json
    {
      "status": "healthy",
      "database": "connected",
      "cache": {"cache": "connected", "used_memory_human": "1.2MB"},
      "tasks": {"tasks": "connected", "queued": 0}
    }
    ```
    """
    result = {
        "status": "healthy",
        "database": "connected",
    }

    # Check DB connectivity
    try:
        await db.execute(text("SELECT 1"))
        result["database"] = "connected"
        logger.debug("Health check: DB OK")
    except Exception as e:
        logger.error("Health check: DB error: %s", e, exc_info=True)
        result["database"] = f"error: {str(e)}"
        result["status"] = "degraded"

    # Check cache
    cache_status = cache_service.health_check()
    result["cache"] = cache_status

    if cache_status.get("cache") == "error":
        logger.warning("Health check: cache error: %s", cache_status.get("detail"))
        result["status"] = "degraded"

    # Check background tasks
    tasks_status = bg_task_service.health_check()
    result["tasks"] = tasks_status

    if tasks_status.get("tasks") == "error":
        logger.warning("Health check: tasks error: %s", tasks_status.get("detail"))
        result["status"] = "degraded"

    logger.info("Health check result: status=%s db=%s cache=%s tasks=%s",
                result["status"], result["database"],
                cache_status.get("cache"), tasks_status.get("tasks"))
    return result


@router.get("/health/verbose")
async def health_check_verbose(
    db: AsyncSession = Depends(get_db)
):
    """Verbose health check with additional metrics.
    
    Returns database metrics, queue stats, and full system status.
    """
    result = {
        "status": "healthy",
        "database": "connected",
        "cache": cache_service.health_check(),
        "tasks": bg_task_service.health_check(),
    }

    # DB metrics
    try:
        db_result = await db.execute(select(func.count(Appointment.id)))
        result["database"] = {
            "status": "connected",
            "total_appointments": db_result.scalar() or 0,
        }
        logger.debug("Health verbose: total_appointments=%d", db_result.scalar() or 0)
    except Exception as e:
        logger.error("Health verbose: DB metrics error: %s", e, exc_info=True)
        result["database"] = f"error: {str(e)}"
        result["status"] = "degraded"

    # Queue stats
    if bg_task_service.enabled:
        result["queue_stats"] = bg_task_service.get_queue_stats()

    return result
