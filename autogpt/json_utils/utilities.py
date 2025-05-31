"""Utilities for the json_fixes package."""
import ast
import json
import os.path
from typing import Any, Literal

from jsonschema import Draft7Validator

from autogpt.config import Config
from autogpt.logs import logger

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


def llm_response_schema(
    config: Config, schema_name: str = LLM_DEFAULT_RESPONSE_FORMAT
) -> dict[str, Any]:
    filename = os.path.join(os.path.dirname(__file__), f"{schema_name}.json")
    with open(filename, "r") as f:
        try:
            json_schema = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load JSON schema: {e}")
    if config.openai_functions:
        del json_schema["properties"]["command"]
        json_schema["required"].remove("command")
    return json_schema


def validate_dict(
    object: object, config: Config, schema_name: str = LLM_DEFAULT_RESPONSE_FORMAT
) -> tuple[Literal[True], None] | tuple[Literal[False], list]:
    """
    :type schema_name: object
    :param schema_name: str
    :type json_object: object

    Returns:
        bool: Whether the json_object is valid or not
        list: Errors found in the json_object, or None if the object is valid
    """
    schema = llm_response_schema(config, schema_name)
    validator = Draft7Validator(schema)

    if errors := sorted(validator.iter_errors(object), key=lambda e: e.path):
        for error in errors:
            logger.debug(f"JSON Validation Error: {error}")

        if config.debug_mode:
            logger.error(json.dumps(object, indent=4))
            logger.error("The following issues were found:")

            for error in errors:
                logger.error(f"Error: {error.message}")
        return False, errors

    logger.debug("The JSON object is valid.")

    return True, None
