"""Commands to execute code"""

COMMAND_CATEGORY = "collect_info"
COMMAND_CATEGORY_TITLE = "INFO COLLECTION"

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
    "extract_installation_instructions_from_readme_file",
    "Allows you to extract any installation related instructions that are metioned in the README file of the project",
    {
        "project_path": {
            "type": "string",
            "description": "The name/path of the project under scope",
            "required": True,
        }
    },
)"""
def extract_instructions_from_readme(agent: Agent) -> str:
    """
    """
    ai_name = agent.ai_config.ai_name
    workspace = "auto_gpt_workspace/"
    files_at_root = os.listdir(os.path.join(workspace, project_path))
    project_path = agent.project_path

    readme_files = []
    for f in files_at_root:
        if "readme" in f.lower():
            readme_files.append(f)

    readme_text = ""

    for f in readme_files:
        with open(os.path.join(workspace, project_path, f)) as wpf:
            readme_text += "------>File: {}\n{}\n".format(f, wpf.read())
    
    if readme_text == "":
        return "No readme file found"
    
    system_prompt = "You are an AI assistant that would help a develper in the mission of installing a python project an getting to run. Your task for now is to analyze the text of the readme file of the target project and extract installation related instructions from the given text of readme file(s)."

    query = "Here is the content of the readme file(s). Please extract any information related to installation including step-by-step points, environement, required software and their versions and also any manaual steps that needs to be done.\n\n" + readme_text

    return ask_chatgpt(query, system_prompt)

"""@command(
    "identify_testing_framework",
    "Read all the requirements from requirements files",
    {
        "project_path": {
            "type": "string",
            "description": "The name/path of the project under scope",
            "required": True,
        }
    },
)"""

def identify_testing_framework(project_path: str, agent: Agent) -> str:
    """
    """

    ai_name = agent.ai_config.ai_name
    pass


"""@command(
    "extract_installation_documentation",
    "Read all the requirements from requirements files",
    {
        "project_path": {
            "type": "string",
            "description": "The name/path of the project under scope",
            "required": True,
        }
    },
)"""
def extract_installation_documentation(project_path: str, agent: Agent) -> str:
    """
    """

    ai_name = agent.ai_config.ai_name
    pass


def ask_chatgpt(query, system_message, model="gpt-4o-mini"):
    with open("openai_token.txt") as opt:
        token = opt.read()
    chat = ChatOpenAI(openai_api_key=token, model=model)

    messages = [
        SystemMessage(
            content= system_message
                    ),
        HumanMessage(
            content=query
            )  
    ]
    #response_format={ "type": "json_object" }
    response = chat.invoke(messages)

    return response.content
