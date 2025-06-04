"""Commands to perform operations on files"""

from __future__ import annotations

COMMAND_CATEGORY = "file_operations"
COMMAND_CATEGORY_TITLE = "File Operations"

import contextlib
import hashlib
import os
import os.path
from pathlib import Path
from typing import Generator, Literal

from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.logs import logger
from autogpt.commands.docker_helpers_static import build_image, start_container, execute_command_in_container, write_string_to_file, read_file_from_container, check_image_exists
from .decorators import sanitize_path_arg

Operation = Literal["write", "append", "delete"]


def text_checksum(text: str) -> str:
    """Get the hex checksum for the given text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def operations_from_log(
    log_path: str | Path,
) -> Generator[tuple[Operation, str, str | None], None, None]:
    """Parse the file operations log and return a tuple containing the log entries"""
    try:
        log = open(log_path, "r", encoding="utf-8")
    except FileNotFoundError:
        return

    for line in log:
        line = line.replace("File Operation Logger", "").strip()
        if not line:
            continue
        operation, tail = line.split(": ", maxsplit=1)
        operation = operation.strip()
        if operation in ("write", "append"):
            try:
                path, checksum = (x.strip() for x in tail.rsplit(" #", maxsplit=1))
            except ValueError:
                logger.warn(f"File log entry lacks checksum: '{line}'")
                path, checksum = tail.strip(), None
            yield (operation, path, checksum)
        elif operation == "delete":
            yield (operation, tail.strip(), None)

    log.close()


def file_operations_state(log_path: str | Path) -> dict[str, str]:
    """Iterates over the operations log and returns the expected state.

    Parses a log file at config.file_logger_path to construct a dictionary that maps
    each file path written or appended to its checksum. Deleted files are removed
    from the dictionary.

    Returns:
        A dictionary mapping file paths to their checksums.

    Raises:
        FileNotFoundError: If config.file_logger_path is not found.
        ValueError: If the log file content is not in the expected format.
    """
    state = {}
    for operation, path, checksum in operations_from_log(log_path):
        if operation in ("write", "append"):
            state[path] = checksum
        elif operation == "delete":
            del state[path]
    return state


@sanitize_path_arg("filename")
def is_duplicate_operation(
    operation: Operation, filename: str, agent: Agent, checksum: str | None = None
) -> bool:
    """Check if the operation has already been performed

    Args:
        operation: The operation to check for
        filename: The name of the file to check for
        agent: The agent
        checksum: The checksum of the contents to be written

    Returns:
        True if the operation has already been performed on the file
    """
    # Make the filename into a relative path if possible
    with contextlib.suppress(ValueError):
        filename = str(Path(filename).relative_to(agent.workspace.root))

    state = file_operations_state(agent.config.file_logger_path)
    if operation == "delete" and filename not in state:
        return True
    if operation == "write" and state.get(filename) == checksum:
        return True
    return False


@sanitize_path_arg("filename")
def log_operation(
    operation: Operation, filename: str, agent: Agent, checksum: str | None = None
) -> None:
    """Log the file operation to the file_logger.txt

    Args:
        operation: The operation to log
        filename: The name of the file the operation was performed on
        checksum: The checksum of the contents to be written
    """
    # Make the filename into a relative path if possible
    with contextlib.suppress(ValueError):
        filename = str(Path(filename).relative_to(agent.workspace.root))

    log_entry = f"{operation}: {filename}"
    if checksum is not None:
        log_entry += f" #{checksum}"
    logger.debug(f"Logging file operation: {log_entry}")
    append_to_file(
        agent.config.file_logger_path, f"{log_entry}\n", agent, should_log=False
    )


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
#@sanitize_path_arg("file_path")
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
#@sanitize_path_arg("filename")
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
    write_result = str(write_string_to_file(agent.container.short_id, text, f"{filename}"))
    if write_result=="None":
        return "File written successfully."
    else:
        return write_result
    

@sanitize_path_arg("filename")
def append_to_file(
    filename: str, text: str, agent: Agent, should_log: bool = True
) -> str:
    """Append text to a file

    Args:
        filename (str): The name of the file to append to
        text (str): The text to append to the file
        should_log (bool): Should log output

    Returns:
        str: A message indicating success or failure
    """
    try:
        directory = os.path.dirname(filename)
        os.makedirs(directory, exist_ok=True)
        with open(filename, "a", encoding="utf-8") as f:
            f.write(text)

        if should_log:
            with open(filename, "r", encoding="utf-8") as f:
                checksum = text_checksum(f.read())
            log_operation("append", filename, agent, checksum=checksum)

        return "Text appended successfully."
    except Exception as err:
        return f"Error: {err}"

'''
@command(
    "list_files",
    "Lists Files in a Directory",
    {
        "directory": {
            "type": "string",
            "description": "The directory to list files in",
            "required": True,
        }
    },
)
@sanitize_path_arg("directory")
def list_files(directory: str, agent: Agent) -> str:
    """lists files in a directory recursively

    Args:
        directory (str): The directory to search in

    Returns:
        list[str]: A list of files found in the directory
    """
    print(directory)
    if directory == ".":
        return execute_command_in_container(agent.container, f"ls -R {agent.project_path}")
    else:
        return execute_command_in_container(agent.container, f"ls -R {agent.project_path}/{directory}")
'''