"""Celery application configuration"""
from celery import Celery
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Create Celery app instance
celery_app = Celery(
    "citatum",
    broker=config.celery_broker_url,
    backend=config.celery_result_backend,
    include=[
        "src.tasks.document_tasks",
        "src.tasks.maintenance"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 30 min soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    # Task safety - Late acknowledgment prevents task loss on worker crash
    task_acks_late=True,
    # Result backend - Store results for status tracking
    task_ignore_result=False,
    result_expires=3600,

    # Worker settings
    worker_concurrency=2,

    # Connection settings for better reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    task_routes={
        "src.tasks.document_tasks.document_upload_and_process": {"queue": "default"},
    },

    # Beat schedule for periodic tasks (uncomment when tasks are implemented)
    beat_schedule={
        'cleanup-old-task-records': {
            'task': "src.tasks.maintenance.clean_celery_executions_table",
            'schedule': 3600,  # every hour
            'args': ()
        }
    },
)
celery_app.conf.task_default_queue = "default"
logger.info(f"Celery app configured with broker: {config.celery_broker_url}")
