"""
YAML Validation Tool.
Safely parses YAML content using yaml.safe_load and checks syntax.
"""

from typing import Optional
import yaml
from pydantic import BaseModel, Field


class YamlValidateInput(BaseModel):
    content: str = Field(..., description="YAML formatted string to validate")


class YamlValidateOutput(BaseModel):
    valid: bool
    error: Optional[str] = None
    data_type: Optional[str] = None
    key_count: Optional[int] = None


def yaml_validate(content: str) -> YamlValidateOutput:
    """
    Safely validates YAML content using yaml.safe_load.
    Never uses unsafe or full loader.
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as ye:
        return YamlValidateOutput(
            valid=False,
            error=f"YAML syntax error: {str(ye)}",
        )
    except Exception as e:
        return YamlValidateOutput(
            valid=False,
            error=f"YAML validation error: {str(e)}",
        )

    data_type = type(data).__name__ if data is not None else "None"
    key_count = len(data) if isinstance(data, dict) else (len(data) if isinstance(data, list) else None)

    return YamlValidateOutput(
        valid=True,
        error=None,
        data_type=data_type,
        key_count=key_count,
    )
