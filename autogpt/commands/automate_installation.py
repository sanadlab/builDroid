"""Commands to execute code"""

COMMAND_CATEGORY = "automate_installation"
COMMAND_CATEGORY_TITLE = "AUTO INSTALL"

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

import javalang
from create_files_index import list_java_files

ALLOWLIST_CONTROL = "allowlist"
DENYLIST_CONTROL = "denylist"



"""@command(
    "write_to_file",
    "A",
    {
        "content_to_write": {
            "type": "string",
            "description": "The content that you want to write into the file",
            "required": True,
        }
    },
)"""
def write_to_file(file_path: str, content_to_write: str, mode: str, agent: Agent) -> str:
    """
    """
    ai_name = agent.ai_config.ai_name
    project_path = agent.project_path
    workspace = "execution_agent_workspace/"
    try:
        with open(os.path.join(workspace, project_path, file_path), mode) as t_file:
            t_file.write(content_to_write)
        return "Content was successfully written to the file {}".format(file_path)
    except Exception as e:
        return str(e)