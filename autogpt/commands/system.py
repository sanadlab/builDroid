"""Commands to control the internal state of the program"""

from __future__ import annotations

COMMAND_CATEGORY = "system"
COMMAND_CATEGORY_TITLE = "System"

from typing import NoReturn

from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.commands.docker_helpers_static import execute_command_in_container
from autogpt.logs import logger


@command(
    "goals_accomplished",
    "Goals are accomplished and there is nothing left to do",
    {
        "reason": {
            "type": "string",
            "description": "A summary to the user of how the goals were accomplished",
            "required": True,
        }
    },
)
def task_complete(reason: str, agent: Agent) -> NoReturn:
    """
    A function that takes in a string and exits the program

    Parameters:
        reason (str): A summary to the user of how the goals were accomplished.
    Returns:
        A result string from create chat completion. A list of suggestions to
            improve the code.
    """
    project_path = agent.project_path
    workspace = "auto_gpt_workspace/"
    files_list = [x[0].lower() for x in agent.written_files]
    if "coverage_results.txt" not in files_list:
        return "You cannot claim goal accomplished without running test cases, measuring coverage and saving them to the file 'coverage_results.txt'"
    if "dockerfile" not in files_list:
        return "You have not created a docker file that creates a docker images and installs the project within that image, installs the dependencies and run tests"
    if not any("coverage" in x for x in files_list):
        return "You have not measured the test suite coverage or you did not write it into a file named coverage_results.txt"
    logger.info(title="Shutting down...\n", message=reason)
    quit()
