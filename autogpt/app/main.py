"""The application entry point.  Can be invoked by a CLI or any other front end application."""
import time
import json
import os

import enum
import logging
import math
import signal
import sys
import subprocess
from pathlib import Path
from types import FrameType
from typing import Optional

from colorama import Fore, Style

from autogpt.agents import Agent, AgentThoughts, CommandArgs, CommandName
from autogpt.agents.base import DEFAULT_TRIGGERING_PROMPT
from autogpt.app.spinner import Spinner
from autogpt.commands import COMMAND_CATEGORIES
from autogpt.config import AIConfig, Config
from autogpt.config.config import set_api_token
from autogpt.logs import logger
from autogpt.models.command_registry import CommandRegistry
from autogpt.commands.docker_helpers_static import build_image, start_container, stop_and_remove, check_image_exists, create_persistent_shell, execute_command_in_container, locate_or_import_gradlew

def run_auto_gpt(
    continuous_limit: int,
    ai_settings: str,
    debug: bool,
    stream: bool,
    working_directory: Path,
    experiment_file: str = None
):
    if not experiment_file:
        raise ValueError("Cannot proceed without experiment file")
    # Configure logging before we do anything else.
    logger.set_level(logging.DEBUG if debug else logging.INFO)

    config = Config()

    # HACK: This is a hack to allow the config into the logger without having to pass it around everywhere
    # or import it directly.
    logger.config = config

    config.continuous_limit = continuous_limit
    config.workspace_path = working_directory / "execution_agent_workspace"
    config.chat_stream = stream
    set_api_token(config)
    ai_config = AIConfig.load(working_directory / "ai_settings.yaml")

    # Create a CommandRegistry instance and scan default folder
    command_registry = CommandRegistry.with_command_modules(COMMAND_CATEGORIES, config)

    ai_config.command_registry = command_registry
    agent = Agent(
        triggering_prompt=DEFAULT_TRIGGERING_PROMPT,
        ai_config=ai_config,
        command_registry=command_registry,
        config=config,
        experiment_file=experiment_file,
    )

    run_interaction_loop(agent)

def run_interaction_loop(
    agent: Agent,
) -> None:
    """Run the main interaction loop for the agent.

    Args:
        agent: The agent to run the interaction loop for.

    Returns:
        None
    """
    # These contain both application config and agent config, so grab them here.
    config = agent.config
    ai_config = agent.ai_config
    logger.debug(f"{ai_config.ai_name} System Prompt: {str(agent.prompt_dictionary)}")

    cycle_budget = cycles_remaining = config.continuous_limit

    spinner = Spinner("Thinking...", plain_output=config.plain_output)

    def graceful_agent_interrupt(signum: int, frame: Optional[FrameType]) -> None:
        nonlocal cycle_budget, cycles_remaining, spinner
        if cycles_remaining in [0, 1, math.inf]:
            logger.typewriter_log(
                "Interrupt signal received. Stopping continuous command execution "
                "immediately.",
                Fore.RED,
            )
            sys.exit()
        else:
            restart_spinner = spinner.running
            if spinner.running:
                spinner.stop()

            logger.typewriter_log(
                "Interrupt signal received. Stopping continuous command execution.",
                Fore.RED,
            )
            cycles_remaining -= 1
            if restart_spinner:
                spinner.start()

    # Set up an interrupt signal for the agent.
    signal.signal(signal.SIGINT, graceful_agent_interrupt)

    #########################
    # Application Main Loop #
    #########################

    image_log = ""
    if not check_image_exists(f"{agent.workspace_path}_image:ExecutionAgent"):
        with open("prompt_files/Template.dockerfile") as df:
            dft = df.read()
        with open(os.path.join(agent.workspace_path, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(dft)
        image_log = build_image(agent.workspace_path, f"{agent.workspace_path}_image:ExecutionAgent")
        if image_log.startswith("An error occurred while building the Docker image"):
            print(image_log)
            sys.exit(1)
    agent.container = start_container(f"{agent.workspace_path}_image:ExecutionAgent", f"{agent.exp_number}_{agent.project_path[:10]}")
    agent.shell_socket = create_persistent_shell(agent.container)
    if agent.container is None:
        sys.exit(1)
    subprocess.run(['docker', 'cp', f'{agent.workspace_path}/{agent.project_path}', f'{agent.container.id}:/{agent.project_path}'])
    print(image_log + "Container launched successfully")
    locate_or_import_gradlew(agent)
        
    command_name = None
    command_args = None
    assistant_reply_dict = None
    result = None
    while cycles_remaining >= 0:
        logger.debug(f"Cycle budget: {cycle_budget}; remaining: {cycles_remaining}")
        ########
        # Plan #
        ########
        # Have the agent determine the next action to take.
        time.sleep(0.2)
        with spinner:
            command_name, command_args, assistant_reply_dict = agent.think(command_name, command_args, assistant_reply_dict, result)

        ###############
        # Update User #
        ###############
        # Print the assistant's thoughts and the next command to the user.
        update_user(config, ai_config, command_name, command_args, assistant_reply_dict)

        ##################
        # Get user input #
        ##################
        # First log new-line so user can differentiate sections better in console
        logger.typewriter_log("\n")
        if cycles_remaining != math.inf:
            # Print authorized commands left value
            logger.typewriter_log(
                "CYCLES REMAINING: ", Fore.CYAN, f"{cycles_remaining}"
            )
        cycles_remaining -= 1

        ###################
        # Execute Command #
        ###################
        # Decrement the cycle counter first to reduce the likelihood of a SIGINT
        # happening during command execution, setting the cycles remaining to 1,
        # and then having the decrement set it to 0, exiting the application.
        agent.left_commands = cycles_remaining
        agent.project_path = agent.project_path.replace(".git","")
        result = agent.execute(command_name, command_args)
        
        if result is not None:
            logger.typewriter_log("SYSTEM: ", Fore.YELLOW, result)
        else:
            logger.typewriter_log("SYSTEM: ", Fore.YELLOW, "Unable to execute command")

        os.makedirs("experimental_setups/{}/saved_contexts/{}".format(agent.exp_number, agent.project_path), exist_ok=True)
        agent.save_to_file("experimental_setups/{}/saved_contexts/{}/cycle_{}".format(agent.exp_number, agent.project_path, cycle_budget - cycles_remaining))
    
    print(f"Last cycle. keep_container: {agent.keep_container}")
    agent.shell_socket.close()
    if not agent.keep_container:
        stop_and_remove(agent.container)
    exit()

def update_user(
    config: Config,
    ai_config: AIConfig,
    command_name: CommandName | None,
    command_args: CommandArgs | None,
    assistant_reply_dict: AgentThoughts,
) -> None:
    """Prints the assistant's thoughts and the next command to the user.

    Args:
        config: The program's configuration.
        ai_config: The AI's configuration.
        command_name: The name of the command to execute.
        command_args: The arguments for the command.
        assistant_reply_dict: The assistant's reply.
    """

    logger.typewriter_log(
        f"{ai_config.ai_name.upper()} THOUGHTS:", Fore.YELLOW, str(assistant_reply_dict.get("thoughts", {}))
    )

    if command_name is not None:  
        if command_name.lower().startswith("error"):
            logger.typewriter_log(
                "ERROR: ",
                Fore.RED,
                f"The Agent failed to select an action. "
                f"Error message: {command_name}",
            )
        else:
            # First log new-line so user can differentiate sections better in console
            logger.typewriter_log("\n")
            logger.typewriter_log(
                "NEXT ACTION: ",
                Fore.CYAN,
                f"COMMAND = {Fore.CYAN}{remove_ansi_escape(command_name)}{Style.RESET_ALL}  "
                f"ARGUMENTS = {Fore.CYAN}{command_args}{Style.RESET_ALL}",
            )
    else:
        logger.typewriter_log(
            "NO ACTION SELECTED: ",
            Fore.RED,
            f"The Agent failed to select an action.",
        )

def remove_ansi_escape(s: str) -> str:
    return s.replace("\x1B", "")
