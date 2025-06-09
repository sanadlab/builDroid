""" A module for generating custom prompt strings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from buildAnaDroid.models.command_registry import CommandRegistry


class PromptGenerator:
    """
    A class for generating custom prompt strings based on constraints, commands,
        resources, and performance evaluations.
    """

    @dataclass
    class Command:
        label: str
        name: str
        params: dict[str, str]
        function: Optional[Callable]

        def __str__(self) -> str:
            """Returns a string representation of the command."""
            params_string = ", ".join(
                f'"{key}": "{value}"' for key, value in self.params.items()
            )
            return f'{self.label}: "{self.name}", params: ({params_string})'

    commands: list[Command]
    command_registry: CommandRegistry | None


    def __init__(self):
        self.commands = []
        self.command_registry = None
        #self.simple_patterns = []
        self.general_guidelines = ""

    def add_general_guidelines(self, line:str) -> None:
        self.general_guidelines += line

    def add_command(
        self,
        command_label: str,
        command_name: str,
        params: dict[str, str] = {},
        function: Optional[Callable] = None,
    ) -> None:
        """
        Add a command to the commands list with a label, name, and optional arguments.

        *Should only be used by plugins.* Native commands should be added
        directly to the CommandRegistry.

        Args:
            command_label (str): The label of the command.
            command_name (str): The name of the command.
            params (dict, optional): A dictionary containing argument names and their
              values. Defaults to None.
            function (callable, optional): A callable function to be called when
                the command is executed. Defaults to None.
        """

        self.commands.append(
            PromptGenerator.Command(
                label=command_label,
                name=command_name,
                params={name: type for name, type in params.items()},
                function=function,
            )
        )

    def _generate_numbered_list(self, items: list[str], start_at: int = 1) -> str:
        return 
