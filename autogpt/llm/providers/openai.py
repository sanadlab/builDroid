from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any
from unittest.mock import patch
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

import openai
from colorama import Fore, Style
from openai import APIError, RateLimitError, Timeout

from autogpt.llm.base import (
    ChatModelInfo,
    ChatSequence,
    ChatModelResponse,
    EmbeddingModelInfo,
    MessageDict,
    TextModelInfo,
    TText,
)
from autogpt.logs import logger
from autogpt.models.command_registry import CommandRegistry

OPEN_AI_CHAT_MODELS = {
    info.name: info
    for info in [
        ChatModelInfo(
            name="gemini-2.0-flash-lite",
            prompt_token_cost=0.0,
            completion_token_cost=0.0,
            max_tokens=8192,
            supports_functions=False,
        ),
        ChatModelInfo(
            name="gemini-2.0-flash",
            prompt_token_cost=0.0,
            completion_token_cost=0.0,
            max_tokens=8192,
            supports_functions=False,
        ),
        ChatModelInfo(
            name="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            prompt_token_cost=0.000,
            completion_token_cost=0.000,
            max_tokens=8192,
            supports_functions=False,
        ),
        ChatModelInfo(
            name="gpt-3.5-turbo-16k-0301 ",
            prompt_token_cost=0.003,
            completion_token_cost=0.004,
            max_tokens=16384,
            supports_functions=True,
        ),
        ChatModelInfo(
            name="gpt-3.5-turbo-16k-0301 ",
            prompt_token_cost=0.003,
            completion_token_cost=0.004,
            max_tokens=16384,
            supports_functions=True,
        ),
        ChatModelInfo(
            name="gpt-4o-mini",
            prompt_token_cost=0.03,
            completion_token_cost=0.06,
            max_tokens=16384,
        ),
        ChatModelInfo(
            name="gpt-3.5-turbo-0125",
            prompt_token_cost=0.001,
            completion_token_cost=0.002,
            max_tokens=16000,
            supports_functions=True,
        )

    ]
}
# Set aliases for rolling model IDs
chat_model_mapping = {
    "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-16k": "gpt-3.5-turbo-0125",
    "gpt-4": "gpt-4o-mini",
    "gpt-4-32k": "gpt-4o-mini",
}
for alias, target in chat_model_mapping.items():
    alias_info = ChatModelInfo(**OPEN_AI_CHAT_MODELS[target].__dict__)
    alias_info.name = alias
    OPEN_AI_CHAT_MODELS[alias] = alias_info

OPEN_AI_TEXT_MODELS = {
    info.name: info
    for info in [
        TextModelInfo(
            name="text-davinci-003",
            prompt_token_cost=0.02,
            completion_token_cost=0.02,
            max_tokens=4097,
        ),
    ]
}

OPEN_AI_EMBEDDING_MODELS = {
    info.name: info
    for info in [
        EmbeddingModelInfo(
            name="text-embedding-ada-002",
            prompt_token_cost=0.0001,
            max_tokens=8191,
            embedding_dimensions=1536,
        ),
    ]
}

OPEN_AI_MODELS: dict[str, ChatModelInfo | EmbeddingModelInfo | TextModelInfo] = {
    **OPEN_AI_CHAT_MODELS,
    **OPEN_AI_TEXT_MODELS,
    **OPEN_AI_EMBEDDING_MODELS,
}

DEFAULT_MODEL_INFO = ChatModelInfo(
    name="unknown",
    prompt_token_cost=0.000,
    completion_token_cost=0.000,
    max_tokens=8192,
    supports_functions=False,
)

def get_model_info(llm_name: str) -> ChatModelInfo:
    return OPEN_AI_CHAT_MODELS.get(llm_name, ChatModelInfo(
        name=llm_name,
        prompt_token_cost=DEFAULT_MODEL_INFO.prompt_token_cost,
        completion_token_cost=DEFAULT_MODEL_INFO.completion_token_cost,
        max_tokens=DEFAULT_MODEL_INFO.max_tokens,
        supports_functions=DEFAULT_MODEL_INFO.supports_functions,
    ))
