"""Enums for LLM providers"""
from enum import Enum


class DocumentTypeEnum(str, Enum):
    """Enum for document types in embedding operations"""
    DOCUMENT = "document"
    QUERY = "query"
