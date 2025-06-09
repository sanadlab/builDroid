from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Callable, Optional, TypedDict

if TYPE_CHECKING:
    from buildAnaDroid.config import Config

from buildAnaDroid.models.command import Command, CommandParameter

# Unique identifier for buildAnaDroid commands
COMMAND_IDENTIFIER = "command_identifier"

class CommandParameterSpec(TypedDict):
    type: str
    description: str
    required: bool


def command(
    name: str,
    description: str,
    parameters: dict[str, CommandParameterSpec],
    enabled: bool | Callable[[Config], bool] = True,
    disabled_reason: Optional[str] = None,
    aliases: list[str] = [],
) -> Callable[..., Any]:
    """The command decorator is used to create Command objects from ordinary functions."""

    def decorator(func: Callable[..., Any]) -> Command:
        typed_parameters = [
            CommandParameter(
                name=param_name,
                description=parameter.get("description"),
                type=parameter.get("type", "string"),
                required=parameter.get("required", False),
            )
            for param_name, parameter in parameters.items()
        ]
        cmd = Command(
            name=name,
            description=description,
            method=func,
            parameters=typed_parameters,
            enabled=enabled,
            disabled_reason=disabled_reason,
            aliases=aliases,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        wrapper.command = cmd

        setattr(wrapper, COMMAND_IDENTIFIER, True)

        return wrapper

    return decorator
