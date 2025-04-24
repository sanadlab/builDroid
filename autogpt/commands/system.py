"""Commands to control the internal state of the program"""

from __future__ import annotations

COMMAND_CATEGORY = "system"
COMMAND_CATEGORY_TITLE = "System"

import docker
from typing import NoReturn
import os
from pathlib import Path
import subprocess
from autogpt.agents.agent import Agent
from autogpt.command_decorator import command
from autogpt.commands.docker_helpers_static import execute_command_in_container, stop_and_remove
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

    client = docker.from_env()
    container = client.containers.get(agent.container.id)
    
    exit_code, output = container.exec_run(f"/bin/sh -c \"find {agent.project_path} -type f -name '*.apk'\"")
    apk_paths = output.decode().strip().split("\n")
    apk_paths = [path for path in apk_paths if path] 
    
    if not apk_paths:
        return "You have not successfully built the project since there is no .apk file in the container."
    for apk_path in apk_paths:
        try:
            host_apk_path = f"experimental_setups/{agent.exp_number}/files/{agent.project_path}"
            os.makedirs(host_apk_path, exist_ok=True)
            subprocess.run(['docker', 'cp', f'{agent.container.id}:/{apk_path}', host_apk_path], check=True)
        except Exception as e:
            print(f"<ERROR> Failed to extract {apk_path}: {e}")
    
    #if "coverage_results.txt" not in files_list:
    #    return "You cannot claim goal accomplished without running test cases, measuring coverage and saving them to the file 'coverage_results.txt'"
    #if "dockerfile" not in files_list:
    #    return "You have not created a docker file that creates a docker images and installs the project within that image, installs the dependencies and run tests"
    #if not any("coverage" in x for x in files_list):
    #    return "You should write test results into a file called: coverage_results.txt"
    #else:
    #    for file in agent.written_files:
    #        if "coverage" in file[0].lower():
    #            condition1 = "coverage" in file[0].lower()
    #            condition2 = any(x not in files[1].lower() for x in ["Tests run:", "Tests passed:", "Tests failed:", "Tests skipped:"])
    #            if not condition1 and not condition2:
    #                pass
    #            break
    #    else:
    #        if condition1:
    #            return "You have to measure test suite coverage, N/A is not an acceptable value"
    #        elif condition2:
    #            return "The coverage_results file should have the following format:\n"+ """Tests run: [PUT CONCRETE VALUE HERE]
#Tests passed: [PUT CONCRETE VALUE HERE]
#Tests failed: [PUT CONCRETE VALUE HERE]
#Tests skipped: [PUT CONCRETE VALUE HERE]
#Average coverage: [PUT CONCRETE VALUE HERE]
#                    """
    logger.info(title="Shutting down...\n", message=reason)
    #if not agent.keep_container and agent.container != None:
        #stop_and_remove(agent.container)
        #os.system("docker system prune -af")
    with open(os.path.join("experimental_setups", agent.exp_number, "saved_contexts", agent.project_path, "SUCCESS"), "w") as ssf:
        ssf.write("SUCCESS")
    quit()
