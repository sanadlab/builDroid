"""Utilities for the json_fixes package."""
import ast
import json
import os.path
from typing import Any, Literal

from jsonschema import Draft7Validator

from buildAnaDroid.config import Config
from buildAnaDroid.logs import logger

LLM_DEFAULT_RESPONSE_FORMAT = "llm_response_format_1"


def extract_dict_from_response(response_string: str) -> dict[str, Any]:    
    try:
        # Attempt a direct parse
        return json.loads(response_string)
    except json.JSONDecodeError:
        # If direct parse fails, attempt to find JSON within the string
        start_index = response_string.find('{')
        end_index = response_string.rfind('}')
        try:
            json_string = response_string[start_index:end_index + 1]
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response string: {e}")
            return {"command": {"name": "missing_command", "args": {}}, "thoughts": "Failed to understand the LLM response."}
