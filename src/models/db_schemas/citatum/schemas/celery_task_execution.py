from src.models.db_schemas.citatum.citatum_base import CitatumBase
from sqlalchemy import Column, DateTime, func, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Index
import uuid


class CeleryTaskExecution(CitatumBase):

    __tablename__ = "celery_task_executions"

    execution_id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        nullable=False,
        server_default=func.uuid_generate_v4()
    )

    task_name = Column(String(255), nullable=False)
    # SHA-256 hash of task arguments
    task_args_hash = Column(String(64), nullable=False)
    celery_task_id = Column(UUID(as_uuid=True), nullable=True)

    status = Column(String(20), nullable=False, default='PENDING')

    task_args = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True),
                        onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('ixz_task_name_args_celery_hash', task_name,
              task_args_hash, celery_task_id, unique=True),
        Index('ixz_task_execution_status', status),
        Index('ixz_task_execution_created_at', created_at),
        Index('ixz_celery_task_id', celery_task_id),
    )
