"""
JSON Validation Tool.
Parses JSON strings safely and verifies structural validity and optional schema expectations.
"""

import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class JsonValidateInput(BaseModel):
    content: str = Field(..., description="JSON string content to validate")
    expected_type: Optional[str] = Field(None, description="Expected root JSON type: 'object' or 'array'")


class JsonValidateOutput(BaseModel):
    valid: bool
    error: Optional[str] = None
    data_type: Optional[str] = None
    key_count: Optional[int] = None
    item_count: Optional[int] = None


def json_validate(content: str, expected_type: Optional[str] = None) -> JsonValidateOutput:
    """
    Safely parses JSON content without code execution.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as jde:
        return JsonValidateOutput(
            valid=False,
            error=f"JSONDecodeError at line {jde.lineno}, col {jde.colno}: {jde.msg}",
        )
    except Exception as e:
        return JsonValidateOutput(
            valid=False,
            error=f"JSON parsing failed: {str(e)}",
        )

    data_type = "object" if isinstance(data, dict) else ("array" if isinstance(data, list) else type(data).__name__)

    if expected_type and data_type != expected_type:
        return JsonValidateOutput(
            valid=False,
            error=f"Expected root type '{expected_type}', got '{data_type}'.",
            data_type=data_type,
        )

    key_count = len(data) if isinstance(data, dict) else None
    item_count = len(data) if isinstance(data, list) else None

    return JsonValidateOutput(
        valid=True,
        error=None,
        data_type=data_type,
        key_count=key_count,
        item_count=item_count,
    )
