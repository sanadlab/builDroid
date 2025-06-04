"""Commands to execute code"""

COMMAND_CATEGORY = "execute_code"
COMMAND_CATEGORY_TITLE = "Execute Code"

import os
import subprocess
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound
from docker.models.containers import Container as DockerContainer
from autogpt.commands.docker_helpers_static import execute_command_in_container
from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.config import Config
from autogpt.logs import logger

from .decorators import sanitize_path_arg

ALLOWLIST_CONTROL = "allowlist"
DENYLIST_CONTROL = "denylist"

def extract_java_home_export(command: str) -> str:
    """
    Extracts the 'export JAVA_HOME=...' portion from a shell command line,
    stopping at '&&' or any Gradle-related call.
    """
    # Split by '&&' to separate env from build
    parts = command.split('&&')
    for part in parts:
        if 'export JAVA_HOME' in part:
            return part.strip()
    return ''  # If not found

@command(
    "linux_terminal",
    "Executes a Shell Command, non-interactive commands only",
    {
        "command": {
            "type": "string",
            "description": "The command line to execute",
            "required": True,
        }
    },
    enabled=True,
    disabled_reason="You are not allowed to run local shell commands. To execute"
    " shell commands, EXECUTE_LOCAL_COMMANDS must be set to 'True' "
    "in your config file: .env - do not attempt to bypass the restriction.",
)
def execute_shell(command: str, agent: Agent) -> str:
    """Execute a shell command and return the output

    Args:
        command (str): The command line to execute

    Returns:
        str: The output of the command
    """

    if "nano " in command:
        return "You cannot execute call nano because it's an interactive command."
    elif "docker " in command:
        if agent.container:
            return "You cannot execute docker commands. You already have access to a running container. If you are facing issues such as missing requirement or need to install a package, you can use linux_terminal to interact with the already running container and install or change whatever you want there. You cannot create another container"
        else:
            return "You cannot execute docker commands. Use the command write_to_file to create a dockerfile script which will automatically build and launch a container. If you are facing build error or issues, you can simplify your dockerfile script to reduce the source of errors"
    elif command.startswith("bash "):
        command = command.replace("bash ", "")
    
    if command == "ls -R":
        return "This command usually returns too much output, hence, it is not allowed."
    current_dir = Path.cwd()
    if not current_dir.is_relative_to(agent.config.workspace_path):
        os.chdir(os.path.join(agent.config.workspace_path, agent.project_path))
    print(f"Executing command '{command}' in container {agent.container.name}...")
    output = execute_command_in_container(agent.shell_socket, command)
    os.chdir(current_dir)
    return output
