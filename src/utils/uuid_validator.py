"""UUID validation utilities for route parameters"""
import uuid
from typing import Optional
from fastapi import HTTPException, status


def validate_uuid(uuid_string: str, param_name: str = "ID") -> str:
    """
    Validate that a string is a valid UUID format.
    
    Args:
        uuid_string: String to validate as UUID
        param_name: Name of the parameter for error messages (e.g., "document_id", "topic_id")
    
    Returns:
        The validated UUID string
    
    Raises:
        HTTPException: If the string is not a valid UUID format
    """
    if not uuid_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{param_name} cannot be empty"
        )
    
    try:
        # Try to parse as UUID - this validates the format
        uuid.UUID(uuid_string)
        return uuid_string
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} format: '{uuid_string}'. Expected a valid UUID (e.g., '550e8400-e29b-41d4-a716-446655440000')"
        )


def is_valid_uuid(uuid_string: Optional[str]) -> bool:
    """
    Check if a string is a valid UUID format without raising an exception.
    
    Args:
        uuid_string: String to check
    
    Returns:
        True if valid UUID, False otherwise
    """
    if not uuid_string:
        return False
    
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
