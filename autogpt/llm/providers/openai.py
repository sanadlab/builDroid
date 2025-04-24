from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any
from unittest.mock import patch
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

import openai
import openai.api_resources.abstract.engine_api_resource as engine_api_resource
from colorama import Fore, Style
from openai.error import APIError, RateLimitError, ServiceUnavailableError, Timeout
from openai.openai_object import OpenAIObject

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

def meter_api(func: Callable):
    """Adds ApiManager metering to functions which make OpenAI API calls"""
    from autogpt.llm.api_manager import ApiManager

    api_manager = ApiManager()

    openai_obj_processor = openai.util.convert_to_openai_object

    def update_usage_with_response(response: OpenAIObject):
        try:
            usage = response.usage
            logger.debug(f"Reported usage from call to model {response.model}: {usage}")
            api_manager.update_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens if "completion_tokens" in usage else 0,
                response.model,
            )
        except Exception as err:
            pass
            #logger.warn(f"Failed to update API costs: {err.__class__.__name__}: {err}")

    def metering_wrapper(*args, **kwargs):
        openai_obj = openai_obj_processor(*args, **kwargs)
        if isinstance(openai_obj, OpenAIObject) and "usage" in openai_obj:
            update_usage_with_response(openai_obj)
        return openai_obj

    def metered_func(*args, **kwargs):
        with patch.object(
            engine_api_resource.util,
            "convert_to_openai_object",
            side_effect=metering_wrapper,
        ):
            return func(*args, **kwargs)

    return metered_func


def retry_api(
    max_retries: int = 10,
    backoff_base: float = 1.0,
    warn_user: bool = True,
):
    """Retry an OpenAI API call.

    Args:
        num_retries int: Number of retries. Defaults to 10.
        backoff_base float: Base for exponential backoff. Defaults to 2.
        warn_user bool: Whether to warn the user. Defaults to True.
    """
    error_messages = {
        ServiceUnavailableError: f"{Fore.RED}Error: The OpenAI API engine is currently overloaded{Fore.RESET}",
        RateLimitError: f"{Fore.RED}Error: Reached rate limit{Fore.RESET}",
    }
    api_key_error_msg = (
        f"Please double check that you have setup a "
        f"{Fore.CYAN + Style.BRIGHT}PAID{Style.RESET_ALL} OpenAI API Account. You can "
        f"read more here: {Fore.CYAN}https://docs.agpt.co/setup/#getting-an-api-key{Fore.RESET}"
    )
    backoff_msg = f"{Fore.RED}Rate Limit Reached. Waiting {{backoff}} seconds...{Fore.RESET}"

    def _wrapper(func: Callable):
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            user_warned = not warn_user
            max_attempts = max_retries + 1  # +1 for the first attempt
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except (RateLimitError, ServiceUnavailableError) as e:
                    error_msg = error_messages[type(e)]
                    #logger.warn(error_msg)

                except (APIError, Timeout) as e:
                    logger.warn(backoff_msg.format(backoff=backoff))
                    if (e.http_status not in [429, 502]) or (attempt == max_attempts):
                        raise

                backoff = backoff_base ** (attempt + 2)
                time.sleep(backoff)

        return _wrapped

    return _wrapper

def retry_gemini_api(
    max_retries: int = 10,
    backoff_base: float = 1.0,
    warn_user: bool = True,
):
    """Retry a Gemini API call.

    Args:
        max_retries int: Number of retries. Defaults to 10.
        backoff_base float: Base for exponential backoff. Defaults to 2.
        warn_user bool: Whether to warn the user. Defaults to True.
    """
    error_messages = {
        ServiceUnavailable: f"{Fore.RED}Error: The Gemini API engine is currently overloaded{Fore.RESET}",
        ResourceExhausted: f"{Fore.RED}Error: Reached rate limit for Gemini API{Fore.RESET}",
    }
    api_key_error_msg = (
        f"Please double check that you have setup a "
        f"{Fore.CYAN + Style.BRIGHT}PAID{Style.RESET_ALL} Gemini API Account. You can "
        f"read more here: {Fore.CYAN}https://ai.google.dev/{Fore.RESET}"  # Replace with actual Gemini API setup link
    )
    backoff_msg = f"{Fore.RED}Rate Limit Reached. Waiting {{backoff}} seconds...{Fore.RESET}"
    error_msg = f"{Fore.RED}Unknown Error. Waiting {{backoff}} seconds...{Fore.RESET}"


    def _wrapper(func: Callable):
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            user_warned = not warn_user
            max_attempts = max_retries + 1  # +1 for the first attempt
            for attempt in range(1, max_attempts + 1):
                backoff = backoff_base ** (attempt + 2)
                try:
                    return func(*args, **kwargs)

                except (ResourceExhausted, ServiceUnavailable) as e:
                    logger.warn(backoff_msg.format(backoff=backoff))
                    if attempt >= max_attempts:
                        raise

                    error_msg = error_messages[type(e)]
                    #logger.warn(error_msg)
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

        return _wrapped

    return _wrapper

@meter_api
@retry_api()
def create_chat_completion(
    messages: List[MessageDict],
    *_,
    **kwargs,
) -> OpenAIObject:
    """Create a chat completion using the OpenAI API

    Args:
        messages: A list of messages to feed to the chatbot.
        kwargs: Other arguments to pass to the OpenAI API chat completion call.
    Returns:
        OpenAIObject: The ChatCompletion response from OpenAI

    """
    completion: OpenAIObject = openai.ChatCompletion.create(
        messages=messages,
        **kwargs,
    )
    if not hasattr(completion, "error"):
        logger.debug(f"Response: {completion}")
    return completion

@meter_api
@retry_gemini_api()
def _create_gemini_completion(
    prompt: ChatSequence,
    key: str,
    model: str,
    chat_completion_kwargs: Dict[str, Any]
) -> ChatModelResponse:

    genai.configure(api_key=key) # Reuse API key.  Rename in Config for clarity
    gemini_model = genai.GenerativeModel(model) # Pass the model explicitly
    chat_completion_kwargs.pop("model", None)

    logger.debug(prompt.dump())

    if "max_tokens" in chat_completion_kwargs:
        chat_completion_kwargs["max_output_tokens"] = chat_completion_kwargs.pop("max_tokens") # Rename the key

    gemini_generation_config = {
        "temperature": chat_completion_kwargs.get("temperature"),
        "max_output_tokens": chat_completion_kwargs.get("max_output_tokens"),
        # Add other relevant Gemini-specific parameters here
    }
    # Remove None values so as not to pass these into the model.
    gemini_generation_config = {k: v for k, v in gemini_generation_config.items() if v is not None}
    
    response = gemini_model.generate_content(
        [message["content"] for message in prompt.raw()],  # Gemini expects a list of turns.
        generation_config=genai.types.GenerationConfig(**gemini_generation_config) # Apply temp, max_tokens
    )

    logger.debug(f"Gemini Response: {response}")

    content = response.text  # Gemini provides the text directly.  Handle None appropriately

    return ChatModelResponse(
        model_info=get_model_info(model),  # Adapt the model info retrieval
        content=content,
        function_call=None, #  Gemini does not have function calls.  Handle this gracefully
    )

@meter_api
@retry_api()
def create_embedding(
    input: str | TText | List[str] | List[TText],
    *_,
    **kwargs,
) -> OpenAIObject:
    """Create an embedding using the OpenAI API

    Args:
        input: The text to embed.
        kwargs: Other arguments to pass to the OpenAI API embedding call.
    Returns:
        OpenAIObject: The Embedding response from OpenAI

    """
    return openai.Embedding.create(
        input=input,
        **kwargs,
    )


@dataclass
class OpenAIFunctionCall:
    """Represents a function call as generated by an OpenAI model

    Attributes:
        name: the name of the function that the LLM wants to call
        arguments: a stringified JSON object (unverified) containing `arg: value` pairs
    """

    name: str
    arguments: str


@dataclass
class OpenAIFunctionSpec:
    """Represents a "function" in OpenAI, which is mapped to a Command in Auto-GPT"""

    name: str
    description: str
    parameters: dict[str, ParameterSpec]

    @dataclass
    class ParameterSpec:
        name: str
        type: str  # TODO: add enum support
        description: Optional[str]
        required: bool = False

    @property
    def schema(self) -> dict[str, str | dict | list]:
        """Returns an OpenAI-consumable function specification"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    param.name: {
                        "type": param.type,
                        "description": param.description,
                    }
                    for param in self.parameters.values()
                },
                "required": [
                    param.name for param in self.parameters.values() if param.required
                ],
            },
        }

    @property
    def prompt_format(self) -> str:
        """Returns the function formatted similarly to the way OpenAI does it internally:
        https://community.openai.com/t/how-to-calculate-the-tokens-when-using-function-call/266573/18

        Example:
        ```ts
        // Get the current weather in a given location
        type get_current_weather = (_: {
        // The city and state, e.g. San Francisco, CA
        location: string,
        unit?: "celsius" | "fahrenheit",
        }) => any;
        ```
        """

        def param_signature(p_spec: OpenAIFunctionSpec.ParameterSpec) -> str:
            # TODO: enum type support
            return (
                f"// {p_spec.description}\n" if p_spec.description else ""
            ) + f"{p_spec.name}{'' if p_spec.required else '?'}: {p_spec.type},"

        return "\n".join(
            [
                f"// {self.description}",
                f"type {self.name} = (_ :{{",
                *[param_signature(p) for p in self.parameters.values()],
                "}) => any;",
            ]
        )


def get_openai_command_specs(
    command_registry: CommandRegistry,
) -> list[OpenAIFunctionSpec]:
    """Get OpenAI-consumable function specs for the agent's available commands.
    see https://platform.openai.com/docs/guides/gpt/function-calling
    """
    return [
        OpenAIFunctionSpec(
            name=command.name,
            description=command.description,
            parameters={
                param.name: OpenAIFunctionSpec.ParameterSpec(
                    name=param.name,
                    type=param.type,
                    required=param.required,
                    description=param.description,
                )
                for param in command.parameters
            },
        )
        for command in command_registry.commands.values()
    ]


def count_openai_functions_tokens(
    functions: list[OpenAIFunctionSpec], for_model: str
) -> int:
    """Returns the number of tokens taken up by a set of function definitions

    Reference: https://community.openai.com/t/how-to-calculate-the-tokens-when-using-function-call/266573/18
    """
    from autogpt.llm.utils import count_string_tokens

    return count_string_tokens(
        f"# Tools\n\n## functions\n\n{format_function_specs_as_typescript_ns(functions)}",
        for_model,
    )


def format_function_specs_as_typescript_ns(functions: list[OpenAIFunctionSpec]) -> str:
    """Returns a function signature block in the format used by OpenAI internally:
    https://community.openai.com/t/how-to-calculate-the-tokens-when-using-function-call/266573/18

    For use with `count_string_tokens` to determine token usage of provided functions.

    Example:
    ```ts
    namespace functions {

    // Get the current weather in a given location
    type get_current_weather = (_: {
    // The city and state, e.g. San Francisco, CA
    location: string,
    unit?: "celsius" | "fahrenheit",
    }) => any;

    } // namespace functions
    ```
    """

    return (
        "namespace functions {\n\n"
        + "\n\n".join(f.prompt_format for f in functions)
        + "\n\n} // namespace functions"
    )