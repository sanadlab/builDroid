"""Commands to control the internal state of the program"""

from __future__ import annotations

COMMAND_CATEGORY = "system"
COMMAND_CATEGORY_TITLE = "System"

import docker
from typing import NoReturn
import os
import subprocess
from buildAnaDroid.agents.agent import Agent
from buildAnaDroid.models.command_decorator import command
from buildAnaDroid.commands.docker_helpers_static import stop_and_remove
from buildAnaDroid.logs import logger

@command(
    "goals_accomplished",
    "Exits agent. Call this command if and only if build success and the .apk file is in the container",
    {
        "reason": {
            "type": "string",
            "description": "A summary to the user of how the goals were accomplished",
            "required": True,
        }
    },
)
def goals_accomplished(reason: str, agent: Agent) -> NoReturn:
    """
    A function that takes in a string and exits the program

    Parameters:
        reason (str): A summary to the user of how the goals were accomplished.
    Returns:
        A result string from create chat completion. A list of suggestions to
            improve the code.
    """

    client = docker.from_env()
    container = client.containers.get(agent.container.id)
    
    exit_code, output = container.exec_run(f"/bin/sh -c \"find {agent.project_path} -type f -name '*.apk'\"")
    apk_paths = output.decode().strip().split("\n")
    apk_paths = [path for path in apk_paths if path] 
    
    if not apk_paths:
        return "You have not successfully built the project since there is no .apk file in the container. Command `goals_accomplished` is used only for build success. Do not use the command until you have built a working .apk file. DO NOT call this command on build failures. Instead, attempt different kinds of approaches to the problem. Try again."
    for apk_path in apk_paths:
        try:
            host_apk_path = f"tests/{agent.project_path}/output"
            os.makedirs(host_apk_path, exist_ok=True)
            subprocess.run(['docker', 'cp', f'{agent.container.id}:/{apk_path}', host_apk_path], check=True)
        except Exception as e:
            print(f"<ERROR> Failed to extract {apk_path}: {e}")
            
    logger.info(title=f"Shutting down... \n", message=reason)
    agent.shell_socket.close()
    with open(os.path.join("tests", agent.project_path, "saved_contexts", "SUCCESS"), "w") as ssf:
        ssf.write("SUCCESS")
    return "goals_accomplished: SUCCESS"
