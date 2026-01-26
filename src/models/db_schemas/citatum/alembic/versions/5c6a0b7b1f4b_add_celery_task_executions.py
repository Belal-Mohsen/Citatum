"""add_celery_task_executions

Revision ID: 5c6a0b7b1f4b
Revises: 1107665699b7
Create Date: 2026-01-26 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c6a0b7b1f4b'
down_revision: Union[str, None] = '1107665699b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure UUID extension exists (noop if already installed)
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        'celery_task_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('task_args_hash', sa.String(length=64), nullable=False),
        sa.Column('celery_task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'PENDING'::text")),
        sa.Column('task_args', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('execution_id')
    )
    op.create_index('ixz_task_name_args_celery_hash', 'celery_task_executions', ['task_name', 'task_args_hash', 'celery_task_id'], unique=True)
    op.create_index('ixz_task_execution_status', 'celery_task_executions', ['status'], unique=False)
    op.create_index('ixz_task_execution_created_at', 'celery_task_executions', ['created_at'], unique=False)
    op.create_index('ixz_celery_task_id', 'celery_task_executions', ['celery_task_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ixz_celery_task_id', table_name='celery_task_executions')
    op.drop_index('ixz_task_execution_created_at', table_name='celery_task_executions')
    op.drop_index('ixz_task_execution_status', table_name='celery_task_executions')
    op.drop_index('ixz_task_name_args_celery_hash', table_name='celery_task_executions')
    op.drop_table('celery_task_executions')
