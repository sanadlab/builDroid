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
from autogpt.memory.vector import MemoryItem, VectorMemory
from autogpt.commands.docker_helpers_static import build_image, start_container, execute_command_in_container, write_string_to_file, read_file_from_container, check_image_exists
from .decorators import sanitize_path_arg
from .file_operations_utils import read_textual_file

import xml.etree.ElementTree as ET
import yaml

def xml_to_dict(element):
    """ Recursively converts XML elements to a dictionary. """
    if len(element) == 0:
        return element.text
    return {
        element.tag: {
            child.tag: xml_to_dict(child) for child in element
        }
    }

def convert_xml_to_yaml(xml_file):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Convert XML to a dictionary
    xml_dict = xml_to_dict(root)
    
    # Convert the dictionary to a YAML string
    yaml_str = yaml.dump(xml_dict, default_flow_style=False)
    
    return yaml_str

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


"""@command(
    "read_file",
    "Read an existing file",
    {
        "file_path": {
            "type": "string",
            "description": "The path of the file to read",
            "required": True,
        }
    },
)"""
#@sanitize_path_arg("file_path")
def read_file(file_path: str, agent: Agent) -> str:
    """Read a file and return the contents

    Args:
        filename (str): The name of the file to read

    Returns:
        str: The contents of the file
    """
    if not agent.container:
        print("READING FILE FROM OUTSIDE CONTAINER CRAZZZZZZZZZZZZZZZZZZZZZY")
        try:
            workspace = agent.workspace_path
            project_path = agent.project_path
            if file_path.lower().endswith("xml"):
                yaml_content = convert_xml_to_yaml(os.path.join(workspace, project_path, file_path))
                return "The xml file was converted to yaml format for better readability:\n"+ yaml_content
        
            content = read_textual_file(os.path.join(workspace, project_path, file_path), logger)
            return content
            # TODO: invalidate/update memory when file is edited
            file_memory = MemoryItem.from_text_file(content, file_path, agent.config)
            if len(file_memory.chunks) > 1:
                return file_memory.summary

            return content
        except Exception as e:
            return f"Error: {str(e)}"
    else:
        return read_file_from_container(agent.container, os.path.join("/app", agent.project_path, file_path.split("/")[-1]))


def ingest_file(
    filename: str,
    memory: VectorMemory,
) -> None:
    """
    Ingest a file by reading its content, splitting it into chunks with a specified
    maximum length and overlap, and adding the chunks to the memory storage.

    Args:
        filename: The name of the file to ingest
        memory: An object with an add() method to store the chunks in memory
    """
    try:
        logger.info(f"Ingesting file {filename}")
        content = read_file(filename)

        # TODO: differentiate between different types of files
        file_memory = MemoryItem.from_text_file(content, filename)
        logger.debug(f"Created memory: {file_memory.dump(True)}")
        memory.add(file_memory)

        logger.info(f"Ingested {len(file_memory.e_chunks)} chunks from {filename}")
    except Exception as err:
        logger.warn(f"Error while ingesting file '{filename}': {err}")

def update_dockerfile_content(dockerfile_content: str) -> str:
    lines = dockerfile_content.splitlines()
    modified_lines = []
    in_run_command = False

    for line in lines:
        stripped_line = line.strip()
        
        # Check if the line starts with 'RUN' and is not a continuation of a previous 'RUN' command
        if stripped_line.startswith("RUN ") and not in_run_command:
            in_run_command = True
            if stripped_line.endswith("\\"):
                modified_lines.append(line.rstrip())
            else:
                # Add || exit 0 with an error message
                modified_lines.append(line.rstrip() + " || { echo \"Command failed with exit code $?\"; exit 0; }")
                in_run_command = False
        elif in_run_command:
            # Check if the line ends with '\', which indicates continuation
            if stripped_line.endswith("\\"):
                modified_lines.append(line)
            else:
                in_run_command = False
                # Add || exit 0 with an error message
                modified_lines.append(line.rstrip() + " || { echo \"Command failed with exit code $?\"; exit 0; }")
        else:
            modified_lines.append(line)

    return "\n".join(modified_lines)

@command(
    "write_to_file",
    "Writes to a file",
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
    if "COPY" in text:
        return "The usage of command 'COPY' is prohibited inside the Dockerfile script. You should just clone the repository inside the docker images and all the files of that repository would be there. No need to copy."
    #checksum = text_checksum(text)
    #if is_duplicate_operation("write", filename, agent, checksum):
    #    return "Error: File has already been updated."
    agent.written_files.append((filename, text))
    if not agent.container:
        try:
            #directory = os.path.dirname(filename)
            #os.makedirs(directory, exist_ok=True)
            workspace = agent.workspace_path
            print("AGENT RPOJECT PATH:::::::", agent.project_path)
            if (agent.project_path + "/") in filename:
                print("PATH TAKEN FROM HERE 1111")
                full_path = os.path.join(workspace, filename)
            else:
                full_path = os.path.join(workspace, agent.project_path, filename)
                #print("PATH TAKEN FROM HERE 2222")
                #print("FULL PATH++++++", full_path)
                #print(workspace)
                #print(agent.project_path)
                #print(filename)
            #if "dockerfile" in filename.lower():
            #    text = update_dockerfile_content(text)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(text)
            
            log_operation("write", filename, agent, "STATIC CHECK SUM WAS WRITTEN FROM file_operations:write_to_file")
            
            print("DOCKER FILE WAS WRITTEN TO ------ ", full_path)
            
            if "dockerfile" in filename.lower():
                image_log = "IMAGE ALREADY EXISTS"
                if not check_image_exists(agent.project_path.lower()+"_image:ExecutionAgent"):
                    image_log = build_image(os.path.join(workspace, agent.project_path), agent.project_path.lower()+"_image:ExecutionAgent")
                    if image_log.startswith("An error occurred while building the Docker image"):
                        return "The following error occured while trying to build a docker image from the docker script you provide (if the error persists, try to simplify your docker script), please fix it:\n" + image_log
                container = start_container(agent.project_path.lower()+"_image:ExecutionAgent")
                if container is not None:
                    agent.container = container
                    cwd = execute_command_in_container(container, "pwd")
                    return image_log + "\nContainer launched successfuly\n" + "\nThe current working directory within the container is: {}".format(cwd)
                else:
                    return str(image_log) + "\n" + str(container)
            return "File written to successfully."
        except Exception as err:
            return f"Error: {err}"
    else:
        print("Writing file in the container...")
        print("PROJECT_PATH:", agent.project_path)
        print("FILENAME:", filename)
        if "dockerfile" in filename.lower():
            return "You cannot create another docker image, you already have access to a running container. Your next step is to build the project using `./gradlew assembleDebug`. If a pacakge is missing or error happened during installation, you can debug and fix the problem inside the running container by interacting with the linux_terminal tool."
        write_result = str(write_string_to_file(agent.container, text, os.path.join("/app", agent.project_path, filename.split("/")[-1])))
        if write_result=="None":
            if "setup" in filename.lower() or "install" in filename.lower() or ".sh" in filename.lower():
                return "installation script was written successfully, you should not run this script. If test cases were not yet run, you should do that with the help of linux_terminal. If you arleady run test cases successfully, you are done with the task."
            else:
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
def list_files(directory: str, agent: Agent) -> list[str]:
    """lists files in a directory recursively

    Args:
        directory (str): The directory to search in

    Returns:
        list[str]: A list of files found in the directory
    """
    found_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("."):
                continue
            relative_path = os.path.relpath(
                os.path.join(root, file), agent.config.workspace_path
            )
            found_files.append(relative_path)

    return found_files
