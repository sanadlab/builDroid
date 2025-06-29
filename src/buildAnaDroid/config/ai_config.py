"""A module that contains the AIConfig class object that contains the configuration"""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import importlib.resources

import yaml

if TYPE_CHECKING:
    from buildAnaDroid.models.command_registry import CommandRegistry
    from buildAnaDroid.prompts.generator import PromptGenerator

    from .config import Config


class AIConfig:
    """
    A class object that contains the configuration information for the AI

    Attributes:
        ai_name (str): The name of the AI.
        ai_role (str): The description of the AI's role.
        ai_goals (list): The list of objectives the AI is supposed to complete.
        api_budget (float): The maximum dollar value for API calls (0.0 means infinite)
    """

    def __init__(
        self,
        ai_name: str = "",
        ai_role: str = "",
        ai_goals: list[str] = [],
        api_budget: float = 0.0,
    ) -> None:
        """
        Initialize a class instance

        Parameters:
            ai_name (str): The name of the AI.
            ai_role (str): The description of the AI's role.
            ai_goals (list): The list of objectives the AI is supposed to complete.
            api_budget (float): The maximum dollar value for API calls (0.0 means infinite)
        Returns:
            None
        """
        self.ai_name = ai_name
        self.ai_role = ai_role
        self.ai_goals = ai_goals
        self.api_budget = api_budget
        self.prompt_generator: PromptGenerator | None = None
        self.command_registry: CommandRegistry | None = None

    @staticmethod
    def load(ai_settings_file: str | Path) -> "AIConfig":
        """
        Returns class object with parameters (ai_name, ai_role, ai_goals, api_budget)
        loaded from yaml file if yaml file exists, else returns class with no parameters.

        Parameters:
            ai_settings_file (Path): The path to the config yaml file.

        Returns:
            cls (object): An instance of given cls object
        """

        resource_path: Path = importlib.resources.files('buildAnaDroid').joinpath('files', 'ai_settings.yaml')
        try:
            with resource_path.open("r", encoding="utf-8") as file:
                config_params = yaml.load(file, Loader=yaml.FullLoader) or {}
        except FileNotFoundError:
            config_params = {}

        ai_name = config_params.get("ai_name", "")
        ai_role = config_params.get("ai_role", "")
        ai_goals = [
            str(goal).strip("{}").replace("'", "").replace('"', "")
            if isinstance(goal, dict)
            else str(goal)
            for goal in config_params.get("ai_goals", [])
        ]
        api_budget = config_params.get("api_budget", 0.0)

        return AIConfig(ai_name, ai_role, ai_goals, api_budget)

    def construct_full_prompt(
        self, config: Config
    ) -> str:
        """
        Returns a prompt to the user with the class information in an organized fashion.

        Parameters:
            None

        Returns:
            full_prompt (str): A string containing the initial prompt for the user
              including the ai_name, ai_role, ai_goals, and api_budget.
        """

        # Construct full prompt
        full_prompt_parts = {
            "role": f"You are {self.ai_name}, {self.ai_role.rstrip('.')}" +\
            "Your decisions must always be made independently without seeking " +\
            "user assistance. Play to your strengths as an LLM and pursue " +\
            "simple strategies with no legal complications."
        }

        if self.ai_goals:
            full_prompt_parts["goals"] = [
                        "\n## Goals",
                        "For your task, you must fulfill the following goals:",
                        *[f"{i+1}. {goal}" for i, goal in enumerate(self.ai_goals)],
                    ]
            
        additional_constraints: list[str] = []
        if self.api_budget > 0.0:
            additional_constraints["additional constraints"] = (
                f"It takes money to let you run. "
                f"Your API budget is ${self.api_budget:.3f}"
            )

        
        def _generate_commands() -> str:
            command_strings = []
            if self.command_registry:
                command_strings += [
                    f"{str(cmd)}\n"
                    for cmd in self.command_registry.commands.values()
                    if cmd.enabled
                ]
            return "".join(f"{i}. {item}" for i, item in enumerate(command_strings, 1))

        full_prompt_parts["commands"]=[
                "\n## Commands",
                "You have access to the following commands (EXCLUSIVELY):",
                f"{_generate_commands()}",
                "Some commands have error strings in the description; call the function with the error string that appeared in the previous build error. DO NOT call the function of which it's error string is not present in the previous build error.",
            ]

        return full_prompt_parts
