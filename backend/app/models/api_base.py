"""Shared base for the Structura API contract models (Checkpoint 8).

These helpers apply ONLY to the new API models. The Document Graph v1.0 models
keep their own configuration and are never subclassed from here.
"""

import math
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


class ApiModel(BaseModel):
    """Base class for every API contract model: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


# Whitespace-only strings are rejected because the value is stripped first.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _check_json_value(value: Any, path: str) -> None:
    """Raise ValueError unless `value` is plain JSON data.

    Error messages name the offending path and Python type only, never the
    value itself, so nothing sensitive can leak through a validation error.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be a finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} has a non-string key")
            _check_json_value(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} is not JSON-compatible ({type(value).__name__})")


def _validate_json_object(value: dict[str, Any]) -> dict[str, Any]:
    _check_json_value(value, "$")
    return value


# A JSON object: string keys; values are str, int, finite float, bool, null,
# list, or nested object. Used for ApiError.details and envelope meta.
JsonObject = Annotated[dict[str, Any], AfterValidator(_validate_json_object)]
