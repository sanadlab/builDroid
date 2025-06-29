from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from buildAnaDroid.config import AIConfig, Config
    from buildAnaDroid.models.command_registry import CommandRegistry

from buildAnaDroid.utils.json_utils import extract_dict_from_response
from buildAnaDroid.logs import logger

from .base import AgentThoughts, BaseAgent, CommandArgs, CommandName
from google import genai
from google.genai.chats import Chat
from openai import OpenAI, Stream

class Agent(BaseAgent):
    """Agent class for interacting with buildAnaDroid."""

    def __init__(
        self,
        ai_config: AIConfig,
        command_registry: CommandRegistry,
        triggering_prompt: str,
        config: Config,
        chat: Chat | Stream = None,
        metadata: dict = {}
    ):
        super().__init__(
            ai_config=ai_config,
            command_registry=command_registry,
            config=config,
            chat=chat,
            default_cycle_instruction=triggering_prompt,
            metadata = metadata
        )

        self.workspace = config.workspace_path

    def execute(
        self,
        command_name: str | None,
        command_args: dict[str, str] | None,
    ) -> str:
        # Execute command
        if command_name is not None and command_name.lower().startswith("error"):
            result = f"Could not execute command: {command_name}{command_args}"
        else:
            command_result = execute_command(
                command_name=command_name,
                arguments=command_args,
                agent=self,
            )
            if command_result == "goals_accomplished: SUCCESS":
                return command_result
            if len(str(command_result)) < 5000:
                result = f"Command {command_name} returned: " f"{command_result}"
            else:
                result = f"Command {command_name} returned: " f"{str(command_result)[:2000]}  ...  {str(command_result)[-3000:]}" 
                
        return result


    def parse_and_process_response(
        self, llm_response: str, *args, **kwargs
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        
        if not llm_response:
            raise SyntaxError("Assistant response has no text content")
        
        with open("tests/tests_list.txt") as eht:
            exps = eht.read().splitlines()
        with open(os.path.join("tests", exps[-1], "responses", "model_responses_{}".format(self.project_path)), "a+") as patf:
            patf.write(llm_response + "\n")
        assistant_reply_dict = extract_dict_from_response(llm_response)

        if "command" not in assistant_reply_dict:
            assistant_reply_dict["command"] = {"name": "missing_command", "args":{}}
        command_dict = assistant_reply_dict["command"]

        commands_interface = {
            "linux_terminal": ["command"],
            "read_file": ["file_path"],
            "goals_accomplished": ["reason"],
            "write_to_file": ["filename", "text"]
        }

        if command_dict["name"] in list(commands_interface.keys()):
            ref_args = commands_interface[command_dict["name"]]
            if isinstance(command_dict["args"], dict):
                command_args = list(command_dict["args"].keys())
                new_command_dict = {"name": command_dict["name"], "args":{}}
                for k in command_args:
                    if k in ref_args:
                        new_command_dict["args"][k] = command_dict["args"][k]
                
                unmatched_args = [arg for arg in command_args if arg not in ref_args]
                unmatched_ref = [arg for arg in ref_args if arg not in list(new_command_dict["args"].keys())]

                for uarg in unmatched_args:
                    for uref in unmatched_ref:
                        if uarg in uref:
                            new_command_dict["args"][uref] = command_dict["args"][uarg]
                            break
                
                if "project_name" in new_command_dict["args"]:
                    if "_" in new_command_dict["args"]["project_name"]:
                        name_only = new_command_dict["args"]["project_name"].split("_")[0]
                        new_command_dict["args"]["project_name"] = name_only

                assistant_reply_dict["command"] = new_command_dict
            else:
                assistant_reply_dict["command"] = {"name": "unknown_command", "args":{}}
        response = None, None, assistant_reply_dict

        # Print Assistant thoughts
        if assistant_reply_dict != {}:
            # Get command name and arguments
            try:
                command_name, arguments = extract_command(assistant_reply_dict)
                response = command_name, arguments, assistant_reply_dict
            except Exception as e:
                logger.error("Error: \n", str(e))

        return response

def extract_command(
    assistant_reply_json: dict
) -> tuple[str, dict[str, str]]:
    """Parse the response and return the command name and arguments

    Args:
        assistant_reply_json (dict): The response object from the AI
        assistant_reply (ChatModelResponse): The model response from the AI
        config (Config): The config object

    Returns:
        tuple: The command name and arguments

    Raises:
        json.decoder.JSONDecodeError: If the response is not valid JSON

        Exception: If any other error occurs
    """
    try:
        if "command" not in assistant_reply_json:
            return "Error:", {"message": "Missing 'command' object in JSON"}

        if not isinstance(assistant_reply_json, dict):
            return (
                "Error:",
                {
                    "message": f"The previous message sent was not a dictionary {assistant_reply_json}"
                },
            )

        command = assistant_reply_json["command"]
        if not isinstance(command, dict):
            return "Error:", {"message": "'command' object is not a dictionary"}

        if "name" not in command:
            return "Error:", {"message": "Missing 'name' field in 'command' object"}

        command_name = command["name"]

        # Use an empty dictionary if 'args' field is not present in 'command' object
        arguments = command.get("args", {})

        return command_name, arguments
    except json.decoder.JSONDecodeError:
        return "Error:", {"message": "Invalid JSON"}
    # All other errors, return "Error: + error message"
    except Exception as e:
        return "Error:", {"message": str(e)}


def execute_command(
    command_name: str,
    arguments: dict[str, str],
    agent: Agent,
) -> Any:
    """Execute the command and return the result

    Args:
        command_name (str): The name of the command to execute
        arguments (dict): The arguments for the command
        agent (Agent): The agent that is executing the command

    Returns:
        str: The result of the command
    """
    try:
        # Execute a command with the same name or alias, if it exists
        if command := agent.command_registry.get_command(command_name):
            return command(**arguments, agent=agent)
        elif command == "missing_command":
            return "Cannot understand the JSON response. Please ensure the response is in the correct format."
        return f"Cannot execute '{command_name}': unknown command." + " Do not try to use this command again."
    
    except Exception as e:
        return f"Error: {str(e)}"
