from src.core.celery_app import celery_app
from src.utils.config import config
from celery import Task
from src.utils.database import create_db_session_factory
from src.utils.logger import get_logger

import asyncio
from src.utils.idempotency_manager import IdempotencyManager


logger = get_logger(__name__)


@celery_app.task(
    bind=True, name="tasks.maintenance.clean_celery_executions_table",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def clean_celery_executions_table(self):

    return asyncio.run(
        _clean_celery_executions_table(self)
    )


async def _clean_celery_executions_table(task_instance: Task):

    db_client = None

    try:
        db_client = create_db_session_factory(config)

        # Create idempotency manager
        idempotency_manager = IdempotencyManager(db_client, None)

        logger.info("cleaning !!!")
        _ = await idempotency_manager.cleanup_old_tasks(5)

        return True

    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        raise
    finally:
        try:
            if db_client:
                await db_client.close()
        except Exception as e:
            logger.error(f"Task failed while cleaning: {str(e)}")
