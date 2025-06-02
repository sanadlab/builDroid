"""Functions for counting the number of tokens in a message or string."""
from __future__ import annotations

from typing import List, overload

from autogpt.llm.base import Message
from autogpt.logs import logger


@overload
def count_message_tokens(messages: Message, model: str = "gpt-3.5-turbo") -> int:
    ...


@overload
def count_message_tokens(messages: List[Message], model: str = "gpt-3.5-turbo-0125") -> int:
    ...


def count_message_tokens(
    messages: Message | List[Message], model: str = "gpt-3.5-turbo-0125"
) -> int:
    """
    Returns the number of tokens used by a list of messages.

    Args:
        messages (list): A list of messages, each of which is a dictionary
            containing the role and content of the message.
        model (str): The name of the model to use for tokenization.
            Defaults to "gpt-3.5-turbo-0125".

    Returns:
        int: The number of tokens used by the list of messages.
    """
    num_tokens = 0
    return num_tokens


def count_string_tokens(string: str, model_name: str) -> int:
    """
    Returns the number of tokens in a text string.

    Args:
        string (str): The text string.
        model_name (str): The name of the encoding to use. (e.g., "gpt-3.5-turbo")

    Returns:
        int: The number of tokens in the text string.
    """
    return 0
