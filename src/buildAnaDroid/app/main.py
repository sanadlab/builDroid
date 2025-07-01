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
from importlib.resources import files

from colorama import Fore, Style

from buildAnaDroid.agents.agent import Agent, AgentThoughts, CommandArgs, CommandName
from buildAnaDroid.agents.base import DEFAULT_TRIGGERING_PROMPT
from buildAnaDroid.app.spinner import Spinner
from buildAnaDroid.commands import COMMAND_CATEGORIES
from buildAnaDroid.config import AIConfig, Config
from buildAnaDroid.config.config import set_api_token
from buildAnaDroid.logs import logger
from buildAnaDroid.models.command_registry import CommandRegistry
from buildAnaDroid.commands.docker_helpers_static import build_image, start_container, check_image_exists, create_persistent_shell, locate_or_import_gradlew

def run_buildAnaDroid(
    cycle_limit: int,
    ai_settings: str,
    debug: bool,
    conversation: bool,
    working_directory: Path,
    metadata: dict
):
    if not metadata:
        raise ValueError("Cannot proceed without metadata")
    # Configure logging before we do anything else.
    logger.set_level(logging.DEBUG if debug else logging.INFO)

    config = Config()

    # HACK: This is a hack to allow the config into the logger without having to pass it around everywhere
    # or import it directly.
    logger.config = config

    config.cycle_limit = cycle_limit
    config.workspace_path = working_directory / "tests/workspace"
    config.conversation = conversation
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
        metadata=metadata,
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
    agent.project_path = agent.project_path.replace(".git","")

    cycle_budget = cycles_remaining = config.cycle_limit

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
    if not check_image_exists("build-anadroid:0.4.4"):
        dockerfile = files("buildAnaDroid.files").joinpath("Template.dockerfile").read_text(encoding="utf-8")
        with open("tests/Dockerfile", "w", encoding="utf-8") as f:
            f.write(dockerfile)
        image_log = build_image("tests", "build-anadroid:0.4.4")
        if image_log.startswith("An error occurred while building the Docker image"):
            print(image_log)
            sys.exit(1)
    agent.container = start_container(f"build-anadroid:0.4.4", f"{agent.project_path[:63]}")
    agent.shell_socket = create_persistent_shell(agent.container)
    if agent.container is None:
        sys.exit(1)
    subprocess.run(['docker', 'cp', f'tests/{agent.project_path}/workspace/{agent.project_path}', f'{agent.container.id}:/{agent.project_path}'])
    print(image_log + "Container launched successfully")
    locate_or_import_gradlew(agent)
        
    command_name = None
    command_args = None
    assistant_reply_dict = None
    result = None
    while cycles_remaining > 0:
        logger.debug(f"Cycle budget: {cycle_budget}; remaining: {cycles_remaining}")
        ########
        # Plan #
        ########
        # Have the agent determine the next action to take.
        with spinner:
            command_name, command_args, assistant_reply_dict = agent.think(command_name, command_args, assistant_reply_dict, result)

        ###############
        # Update User #
        ###############
        # Print the assistant's thoughts and the next command to the user.
        update_user(config, ai_config, command_name, command_args, assistant_reply_dict)
        logger.typewriter_log("CYCLES REMAINING: ", Fore.CYAN, f"{cycles_remaining}")
        cycles_remaining -= 1

        ###################
        # Execute Command #
        ###################
        # Decrement the cycle counter first to reduce the likelihood of a SIGINT
        # happening during command execution, setting the cycles remaining to 1,
        # and then having the decrement set it to 0, exiting the application.
        agent.left_commands = cycles_remaining
        result = agent.execute(command_name, command_args)
        if result == "goals_accomplished: SUCCESS":
            agent.shell_socket.close()
            return
        if result is not None:
            logger.info(title="SYSTEM: ", title_color=Fore.YELLOW, message=result)
        else:
            logger.info(title="SYSTEM: ", title_color=Fore.YELLOW, message="Unable to execute command")

        os.makedirs("tests/{}/saved_contexts".format(agent.project_path), exist_ok=True)
        agent.save_to_file("tests/{}/saved_contexts/cycle_{}".format(agent.project_path, cycle_budget - cycles_remaining))
    
    logger.info("Last cycle. Shutting down...")
    agent.shell_socket.close()
    return

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
