"""initial_citatum_schema

Revision ID: 1107665699b7
Revises: 
Create Date: 2025-01-09 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1107665699b7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create topics table
    op.create_table(
        'topics',
        sa.Column('topic_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topic_uuid', postgresql.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('topic_name', sa.String(), nullable=False),
        sa.Column('topic_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('topic_id'),
        sa.UniqueConstraint('topic_uuid')
    )
    op.create_index(op.f('ix_topics_topic_uuid'), 'topics', ['topic_uuid'], unique=True)
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('document_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_uuid', postgresql.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_type', sa.String(), nullable=False),
        sa.Column('document_name', sa.String(), nullable=False),
        sa.Column('document_size', sa.Integer(), nullable=False),
        sa.Column('document_title', sa.String(), nullable=True),
        sa.Column('document_author', sa.String(), nullable=True),
        sa.Column('document_publication_date', sa.Date(), nullable=True),
        sa.Column('document_doi', sa.String(), nullable=True),
        sa.Column('document_journal', sa.String(), nullable=True),
        sa.Column('document_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('document_topic_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_topic_id'], ['topics.topic_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id'),
        sa.UniqueConstraint('document_uuid')
    )
    op.create_index(op.f('ix_documents_document_uuid'), 'documents', ['document_uuid'], unique=True)
    op.create_index('ix_document_topic_id', 'documents', ['document_topic_id'], unique=False)
    op.create_index('ix_document_type', 'documents', ['document_type'], unique=False)
    op.create_index('ix_document_doi', 'documents', ['document_doi'], unique=False)
    
    # Create citations table
    op.create_table(
        'citations',
        sa.Column('citation_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('citation_uuid', postgresql.UUID(as_uuid=False), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('citation_text', sa.Text(), nullable=False),
        sa.Column('citation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('citation_order', sa.Integer(), nullable=False),
        sa.Column('citation_page_number', sa.Integer(), nullable=True),
        sa.Column('citation_section', sa.String(), nullable=True),
        sa.Column('citation_topic_id', sa.Integer(), nullable=False),
        sa.Column('citation_document_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['citation_topic_id'], ['topics.topic_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['citation_document_id'], ['documents.document_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('citation_id'),
        sa.UniqueConstraint('citation_uuid')
    )
    op.create_index(op.f('ix_citations_citation_uuid'), 'citations', ['citation_uuid'], unique=True)
    op.create_index('ix_citation_topic_id', 'citations', ['citation_topic_id'], unique=False)
    op.create_index('ix_citation_document_id', 'citations', ['citation_document_id'], unique=False)
    op.create_index('ix_citation_page_number', 'citations', ['citation_page_number'], unique=False)


def downgrade() -> None:
    # Drop citations table
    op.drop_index('ix_citation_page_number', table_name='citations')
    op.drop_index('ix_citation_document_id', table_name='citations')
    op.drop_index('ix_citation_topic_id', table_name='citations')
    op.drop_index(op.f('ix_citations_citation_uuid'), table_name='citations')
    op.drop_table('citations')
    
    # Drop documents table
    op.drop_index('ix_document_doi', table_name='documents')
    op.drop_index('ix_document_type', table_name='documents')
    op.drop_index('ix_document_topic_id', table_name='documents')
    op.drop_index(op.f('ix_documents_document_uuid'), table_name='documents')
    op.drop_table('documents')
    
    # Drop topics table
    op.drop_index(op.f('ix_topics_topic_uuid'), table_name='topics')
    op.drop_table('topics')
