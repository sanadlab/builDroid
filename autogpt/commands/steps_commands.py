"""Commands to execute code"""

COMMAND_CATEGORY = "steps_commands"
COMMAND_CATEGORY_TITLE = "STEPS COMMANDS"

import os
import subprocess
import re
import json
import random
import time

import docker
from docker.errors import DockerException, ImageNotFound
from docker.models.containers import Container as DockerContainer

from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.logs import logger

from create_files_index import list_java_files

ALLOWLIST_CONTROL = "allowlist"
DENYLIST_CONTROL = "denylist"
workspace_folder = "execution_agent_workspace"

"""
    Step 1:
        extract_python_version
        write_python_version_to_file

    Step 2:
        extract_dependencies
        list_files
        read_file
        write_dependencies_to_file

    Step 3:
        create_virtual_environment

    Step 4:
        linux_terminal

    Step 5:
        extract_test_info_from_readme
        list_files
        write_test_commands

    Step 6:
        linux_terminal

    Step 7:
        linux_terminal

    Step 8:
        write_installation_script

    Step 9:
        git (for cloning the repository)
        Dockerfile (for Docker image configuration)


"""

"""@command(
    "extract_language_and_version",
    "",
    {
    },
)"""
def extract_language_and_version(agent: Agent) -> str:
    project_path = agent.project_path
    system_prompt = "You are an assitant that helps analyze README file of a project to extract information relevant to the language of the project and the version."
    query = "Here is the content of the README file of a project on GitHub, your task is to extract information related to the language/version required to install and run the project.\n"
    project_path = agent.project_path
    root_files = os.listdir(os.path.join(workspace_folder, project_path))
    readme_name = ""
    for f in root_files:
        if f.lower() == "readme.md":
            readme_name = f
            break
    else:
        for f in root_files:
            if "readme" in f:
                readme_name = f
                break
        else:
            return "Error: no readme files found"
    with open(os.path.join(workspace_folder, project_path, readme_name)) as fpp:
        readme_content = fpp.read()
    query += readme_content

    return ask_chatgpt(query, system_prompt)

"""@command(
    "write_language_version_to_file",
    "",
    {
        "language_version": {
            "type": "string",
            "description": "",
            "required": True
        }
    },
)"""
def write_language_version_to_file(language_version: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, "LANGUAGE_VERSION.txt"), "w") as lvt:
        lvt.write(language_version)
    return "Language version written successfully"

"""@command(
    "extract_dependencies",
    "",
    {
    },
)"""
def extract_dependencies(agent: Agent) -> str:
    project_path = agent.project_path
    system_prompt = "You are an assitant that helps analyze README file of a project to extract information relevant to the required dependencies to install and run the project."
    query = "Here is the content of the README file of a project on GitHub, your task is to extract information related to the required dependencies (packages, modules, software, system applications...)\n"
    project_path = agent.project_path
    root_files = os.listdir(os.path.join(workspace_folder, project_path))
    readme_name = ""
    for f in root_files:
        if f.lower() == "readme.md":
            readme_name = f
            break
    else:
        for f in root_files:
            if "readme" in f:
                readme_name = f
                break
        else:
            return "Error: no readme files found"
    with open(os.path.join(workspace_folder, project_path, readme_name)) as fpp:
        readme_content = fpp.read()
    query += readme_content

    return ask_chatgpt(query, system_prompt)

"""@command(
    "list_files",
    "",
    {
        
    },
)"""
def list_files(agent: Agent) -> str:
    return os.listdir(os.path.join(workspace_folder, agent.project_path))

@command(
    "read_file",
    "",
    {
        "file_path": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)
def read_file(file_path: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, file_path)) as fpp:
        return "The result of reading the file {}:\n{}".format(file_path, fpp.read())

"""@command(
    "write_dependencies_to_file",
    "",
    {
        "dependecies list": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)"""
def write_dependencies_to_file(dependencies_list: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(workspace_folder, project_path, "DEPENDENCIES_LIST.txt", "w") as dlt:
        dlt.write(dependencies_list)
    return "Dependencies written successfully"

"""@command(
    "write_setup_environment_commands",
    "",
    {
        "commands_list": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)"""
def write_setup_environment_commands(commands_list:str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, "ENVIRONMENT_SETUP.txt"), "w") as est:
        est.write(commands_list)

    commands_list_split = commands_list.split("\n")
    for cmd in commands_list_split:
        execute_shell(cmd)

    return "The setup environment commands were saved into a file and executed"

"""@command(
    "extract_build_and_test_info_from_readme",
    "",
    {
    },
)"""
def extract_build_and_test_info_from_readme(agent: Agent) -> str:
    project_path = agent.project_path
    system_prompt = "You are an assitant that helps analyze README file of a project to extract information relevant to the steps and tools used to build and run tests of the project."
    query = "Here is the content of the README file of a project on GitHub, your task is to extract information about the process/tools used to build and test the project.\n"
    project_path = agent.project_path
    root_files = os.listdir(os.path.join(workspace_folder, project_path))
    readme_name = ""
    for f in root_files:
        if f.lower() == "readme.md":
            readme_name = f
            break
    else:
        for f in root_files:
            if "readme" in f:
                readme_name = f
                break
        else:
            return "Error: no readme files found"
    with open(os.path.join(workspace_folder, project_path, readme_name)) as fpp:
        readme_content = fpp.read()
    query += readme_content
    return ask_chatgpt(query, system_prompt)

"""@command(
    "write_build_test_commands",
    "",
    {
        "commands": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)"""
def write_build_test_commands(commands: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, "BUILD_TEST_COMMANDS.txt"), "w") as btc:
        btc.write(commands)
    
    cmds_split = commands.split("\n")

    execution_results = ""
    for cmd in cmds_split:
        execution_results += execute_shell(cmd)

    with open(os.path.join(workspace_folder, project_path, "BUILD_TEST_RESULTS.txt"), "w") as btr:
        btr.write(execution_results)
    return "Build and test commands were written successfully."

"""@command(
    "write_installation_script",
    "",
    {
        "installation_script": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)"""


def write_installation_script(installation_script: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, "INSTALLATION_SCRIPT.sh"), "w") as insts:
        insts.write(installation_script)

    return "The installation script was written successfully"

"""@command(
    "write_Dockerfile_script",
    "",
    {
        "docker_script": {
            "type": "string",
            "description": "",
            "required": True,
        }
    },
)"""
def write_Dockerfile_script(docker_script: str, agent: Agent) -> str:
    project_path = agent.project_path
    with open(os.path.join(workspace_folder, project_path, "DOCKER_SCRIPT.sh"), "w") as insts:
        insts.write(installation_script)

    return "The docker script was written successfully"


def execute_shell(command_line: str) -> str:
    current_dir = Path.cwd()
    # Change dir into workspace if necessary
    if not current_dir.is_relative_to(workspace_folder):
        os.chdir(workspace_folder)

    logger.info(
        f"Executing command '{command_line}' in working directory '{os.getcwd()}'"
    )

    result = subprocess.run(command_line, capture_output=True, shell=True)
    output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # Change back to whatever the prior working dir was

    os.chdir(current_dir)
    return output