"""Commands to perform operations on files"""

from __future__ import annotations

COMMAND_CATEGORY = "file_operations"
COMMAND_CATEGORY_TITLE = "File Operations"

from buildAnaDroid.agents.agent import Agent
from buildAnaDroid.models.command_decorator import command
from buildAnaDroid.commands.docker_helpers_static import execute_command_in_container

@command(
    "read_file",
    "Read an existing file",
    {
        "file_path": {
            "type": "string",
            "description": "The path of the file to read",
            "required": True,
        }
    },
)
def read_file(file_path: str, agent: Agent) -> str:
    """Read a file and return the contents

    Args:
        filename (str): The name of the file to read

    Returns:
        str: The contents of the file
    """
    return execute_command_in_container(agent.shell_socket, f'cat {file_path}')

@command(
    "write_to_file",
    "Writes to a file (overwrites all content if already exists)",
    {
        "filename": {
            "type": "string",
            "description": "The name of the file to write to",
            "required": True,
        },
        "text": {
            "type": "string",
            "description": "The text to write to the file",
            "required": True,
        },
    },
    aliases=["write_file", "create_file"],
)
def write_to_file(filename: str, text: str, agent: Agent) -> str:
    """Write text to a file

    Args:
        filename (str): The name of the file to write to
        text (str): The text to write to the file

    Returns:
        str: A message indicating success or failure
    """
    print("Writing file in the container...")
    print("FILENAME:", filename)
    if "dockerfile" in filename.lower():
        return "You cannot create another docker image, you already have access to a running container. Your next step is to build the project using `./gradlew assembleDebug`. If a pacakge is missing or error happened during installation, you can debug and fix the problem inside the running container by interacting with the linux_terminal tool."
    command = f"echo -n '{text}' > {filename}"
    write_result = execute_command_in_container(agent.shell_socket, command)
    if write_result=="":
        return "File written successfully."
    else:
        return write_result
    