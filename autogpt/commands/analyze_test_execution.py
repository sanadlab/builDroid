"""Commands to execute code"""

COMMAND_CATEGORY = "analyze_test_execution"
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
    "write_tests_execution_summary",
    "Allows you to extract any installation related instructions that are metioned in the README file of the project",
    {
        "project_path": {
            "type": "string",
            "description": "The name/path of the project under scope",
            "required": True,
        }
    },
)"""
def write_tests_execution_summary(summary: str, agent: Agent) -> str:
    """
    """
   
    project_path = agent.project_path
    workspace = "execution_agent_workspace/"
    with open(os.path.join(workspace, project_path, "tests_execution_summary.txt"), "w") as tes:
        tes.write(summary)

    return "Summary was written successfully"