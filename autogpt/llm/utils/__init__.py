from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Any

from colorama import Fore

from autogpt.config import Config
import google.generativeai as genai
from google.generativeai.generative_models import ChatSession
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from pydantic import BaseModel

from ..api_manager import ApiManager
from ..base import (
    ChatModelResponse,
    ChatSequence,
    FunctionCallDict,
    Message,
    ResponseMessageDict,
)
from ..providers import openai as iopenai
from ..providers.openai import (
    OPEN_AI_CHAT_MODELS,
    OpenAIFunctionCall,
    OpenAIFunctionSpec,
    count_openai_functions_tokens,
    get_model_info
)
from .token_counter import *


def call_ai_function(
    function: str,
    args: list,
    description: str,
    config: Config,
    model: Optional[str] = None,
) -> str:
    """Call an AI function

    This is a magic function that can do anything with no-code. See
    https://github.com/Torantulino/AI-Functions for more info.

    Args:
        function (str): The function to call
        args (list): The arguments to pass to the function
        description (str): The description of the function
        model (str, optional): The model to use. Defaults to None.

    Returns:
        str: The response from the function
    """
    if model is None:
        if config.openai_api_base is None:
            model = config.smart_llm
        else:
            model = config.other_llm
    # For each arg, if any are None, convert to "None":
    args = [str(arg) if arg is not None else "None" for arg in args]
    # parse args to comma separated string
    arg_str: str = ", ".join(args)

    prompt = ChatSequence.for_model(
        model,
        [
            Message(
                "system",
                f"You are now the following python function: ```# {description}"
                f"\n{function}```\n\nOnly respond with your `return` value.",
            ),
            Message("user", arg_str),
        ],
    )
    return send_request(prompt=prompt, temperature=0, config=config).content

def send_request(
    prompt: str,
    config: Config,
    temperature: Optional[float] = None,
    stream: bool = False,
    chat: ChatSession = None,
) -> str:
    """Create a chat completion using either OpenAI or Gemini, based on config."""

    class Command(BaseModel):
        name: str
        args: dict[str, Any]

    class ResponseSchema(BaseModel):
        thoughts: str
        command: Command
        
    chat_completion_kwargs = {
        "temperature": temperature,
        "response_mime_type": "application/json",
        "response_schema": ResponseSchema,
    }

    backoff_base = 1.2
    max_attempts = 5
    # Dispatch to OpenAI or Gemini based on config
    if config.openai_api_base is not None and "google" in config.openai_api_base:
        backoff_msg = f"{Fore.RED}Rate Limit Reached. Waiting {{backoff}} seconds...{Fore.RESET}"
        error_msg = f"{Fore.RED}Unknown Error. Waiting {{backoff}} seconds...{Fore.RESET}"
        for attempt in range(1, max_attempts + 1):
            backoff = round(backoff_base ** (attempt + 2), 2)
            try:
                response = chat.send_message(prompt, stream=stream, generation_config=chat_completion_kwargs)
                full_response = ""
                for chunk in response:
                    full_response += chunk.text
                return full_response

            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warn(backoff_msg.format(backoff=backoff))
                if attempt >= max_attempts:
                    raise
                if False:  # Changed this to `if True` to display the message. Consider a configuration flag.
                    logger.double_check(api_key_error_msg)
                    # Add logging of the exception for debugging
                    logger.debug(f"Gemini API Error: {e}")
                    user_warned = True

            except Exception as e:  # Catch-all for other potential Gemini errorsc
                logger.warn(error_msg.format(backoff=backoff))
                if attempt >= max_attempts:
                    raise  # Re-raise after max retries
                #logger.error(f"Unexpected Gemini API error: {e}")

            time.sleep(backoff)
            
    chat_completion_kwargs.update(config.get_openai_credentials(model))
    response = iopenai.create_chat_completion(messages=prompt.raw(), **chat_completion_kwargs)
    
    logger.debug(f"Response: {response}")

    if hasattr(response, "error"):
        logger.error(response.error)
        raise RuntimeError(response.error)

    first_message: ResponseMessageDict = response.choices[0].message
    content: str | None = first_message.get("content")
    function_call: FunctionCallDict | None = first_message.get("function_call")

    for plugin in config.plugins:
        if not plugin.can_handle_on_response():
            continue
        # TODO: function call support in plugin.on_response()
        content = plugin.on_response(content)

    return ChatModelResponse(
        model_info=OPEN_AI_CHAT_MODELS[model],
        content=content,
        function_call=OpenAIFunctionCall(
            name=function_call["name"], arguments=function_call["arguments"]
        )
        if function_call
        else None,
    )

def create_chat_completion(
    prompt: ChatSequence,
    config: Config,
    functions: Optional[List[OpenAIFunctionSpec]] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ChatModelResponse:
    """Create a chat completion using either OpenAI or Gemini, based on config."""

    if model is None:
        model = prompt.model.name
    if temperature is None:
        temperature = config.temperature
    if max_tokens is None:
        prompt_tlength = prompt.token_length
        max_tokens = OPEN_AI_CHAT_MODELS[model].max_tokens # Default : 4000 for max output token. Reduced if prompt size is large.
        logger.debug(f"Prompt length: {prompt_tlength} tokens")

    logger.info(
        f"{Fore.GREEN}Creating chat completion with model {model}, temperature {temperature}, max_tokens {max_tokens}, prompt_length {prompt.token_length}{Fore.RESET}"
    )

    chat_completion_kwargs = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # "response_format": { "type": "json_object" } # Remove to avoid issues with Gemini.
    }
    chat_completion_kwargs.update(config.get_openai_credentials(model))

    for plugin in config.plugins:
        if plugin.can_handle_chat_completion(
            messages=prompt.raw(),
            **chat_completion_kwargs,
        ):
            message = plugin.handle_chat_completion(
                messages=prompt.raw(),
                **chat_completion_kwargs,
            )
            if message is not None:
                return message

    # Dispatch to OpenAI or Gemini based on config
    if config.openai_api_base is not None and "google" in config.openai_api_base:
        return iopenai._create_gemini_completion(prompt, config.openai_api_key, model, chat_completion_kwargs)
    chat_completion_kwargs.update(config.get_openai_credentials(model))
    response = iopenai.create_chat_completion(messages=prompt.raw(), **chat_completion_kwargs)
    
    logger.debug(f"Response: {response}")

    if hasattr(response, "error"):
        logger.error(response.error)
        raise RuntimeError(response.error)

    first_message: ResponseMessageDict = response.choices[0].message
    content: str | None = first_message.get("content")
    function_call: FunctionCallDict | None = first_message.get("function_call")

    for plugin in config.plugins:
        if not plugin.can_handle_on_response():
            continue
        # TODO: function call support in plugin.on_response()
        content = plugin.on_response(content)

    return ChatModelResponse(
        model_info=OPEN_AI_CHAT_MODELS[model],
        content=content,
        function_call=OpenAIFunctionCall(
            name=function_call["name"], arguments=function_call["arguments"]
        )
        if function_call
        else None,
    )