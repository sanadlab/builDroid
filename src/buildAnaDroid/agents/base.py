from __future__ import annotations
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import time
from colorama import Fore
from abc import ABCMeta, abstractmethod
from typing import Any, Literal, Optional
import json
import os
from importlib.resources import files
import functools

from buildAnaDroid.config import AIConfig, Config
from buildAnaDroid.models.command_registry import CommandRegistry
from google import genai
from google.genai.chats import Chat
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from openai import OpenAI, Stream

from buildAnaDroid.logs import logger
DEFAULT_TRIGGERING_PROMPT = (
    "Determine exactly one command to use based on the given goals "
    "and the progress you have made so far, "
    "and respond using the JSON schema specified previously:"
)

CommandName = str
CommandArgs = dict[str, str]
AgentThoughts = dict[str, Any]

def retry(max_attempts=3, backoff_base=1.5, exceptions_to_catch=(ResourceExhausted, ServiceUnavailable)):
    """
    A decorator to retry a function if an exception occurs.

    :param max_attempts: Maximum number of times to attempt the function.
    :param backoff_base: Factor by which the delay increases each time (e.g., 2 for exponential).
    :param exceptions_to_catch: A tuple of exception types to catch and retry on.
                                Defaults to all exceptions.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            backoff_msg = f"{Fore.RED}Rate Limit Reached. Waiting {{backoff}} seconds...{Fore.RESET}"
            error_msg = f"{Fore.RED}Unknown Error: {{err}}. Waiting {{backoff}} seconds...{Fore.RESET}"
            for attempt in range(1, max_attempts + 1):
                backoff = round(backoff_base ** (attempt), 2)
                try:
                    return func(*args, **kwargs)
                except exceptions_to_catch as e:
                    logger.warn(backoff_msg.format(backoff=backoff))
                    if attempt >= max_attempts:
                        raise
                except Exception as e:  # Catch-all for other potential error
                    logger.warn(error_msg.format(err=e, backoff=backoff))
                    if attempt >= max_attempts:
                        raise
                time.sleep(backoff)
        return wrapper
    return decorator

def create_chat_completion(
    client,
    model,
    prompt
) -> str:
    if type(client) is genai.Client:
        return create_chat_completion_gemini(client, model, prompt)
    elif type(client) is OpenAI:
        return create_chat_completion_gpt(client, model, prompt)
    return "ERROR: Client not supported."

@retry()
def create_chat_completion_gemini(
    client: genai.Client,
    model,
    prompt
) -> str:
    """Create a chat completion with Gemini."""
    response = client.models.generate_content(
        model=model, contents=prompt
    )
    return response.text

@retry()
def create_chat_completion_gpt(
    client: OpenAI,
    model,
    prompt,
) -> str:
    """Create a chat completion with GPT."""
    response = client.responses.create(
        model=model, input=prompt
    )
    return response.output_text
    
@retry()
def send_message_gemini(
    chat: Chat,
    prompt: str
) -> str:
    """Send a message to current chat with Gemini."""
    response = chat.send_message(message=prompt)
    return response.text

@retry()
def send_message_gpt(
    chat: Stream,
    model: str,
    client: OpenAI,
    prompt: str,
) -> str:
    """Send a message to current chat with GPT."""
    chat = client.responses.create(
        model=model, input=prompt,
        previous_response_id=chat.id
    )
    return chat.output_text

class BaseAgent(metaclass=ABCMeta):
    """Base class for all buildAnaDroid agents."""

    ThoughtProcessID = Literal["one-shot"]

    def __init__(
        self,
        ai_config: AIConfig,
        command_registry: CommandRegistry,
        config: Config,
        chat: Chat | Stream = None,
        big_brain: bool = True,
        default_cycle_instruction: str = DEFAULT_TRIGGERING_PROMPT,
        cycle_budget: Optional[int] = 1,
        metadata: dict = {}
    ):
        self.metadata = metadata
        self.ai_config = ai_config
        """The AIConfig or "personality" object associated with this agent."""

        self.command_registry = command_registry
        """The registry containing all commands available to the agent."""

        self.config = config
        """The applicable application configuration."""

        self.big_brain = big_brain
        """
        Whether this agent uses the configured smart LLM (default) to think,
        as opposed to the configured fast LLM.
        """

        self.default_cycle_instruction = default_cycle_instruction
        """The default instruction passed to the AI for a thinking cycle."""

        self.chat = None

        self.cycle_budget = cycle_budget
        """
        The number of cycles that the agent is allowed to run unsupervised.

        `None` for unlimited continuous execution,
        `1` to require user approval for every step,
        `0` to stop the agent.
        """
        self.cycles_remaining = cycle_budget
        """The number of cycles remaining within the `cycle_budget`."""

        self.cycle_count = 0
        """The number of cycles that the agent has run since its initialization."""

        self.prompt_dictionary = ai_config.construct_full_prompt(config)
        
        ### Read static prompt files
        prompt_files = files("buildAnaDroid.prompts.prompt_files").joinpath("cycle_instruction")
        with prompt_files.open("r", encoding="utf-8") as cit:
            self.cycle_instruction = cit.read()

        self.project_path = self.metadata["project_path"]
        self.project_url = self.metadata["project_url"]
        self.workspace_path = "tests/workspace"
        self.past_attempt = self.metadata["past_attempt"]
        
        self.tests_executed = False
        
        self.track_budget = True
        self.left_commands = 0
        self.max_budget = -1

        self.container = None
        self.shell_socket = None

    def to_dict(self):
        return {
            "ai_config": str(self.ai_config),  # Assuming this is a complex object
            "command_registry": str(self.command_registry),  # Assuming this is a complex object
            "config": str(self.config),  # Assuming this is a complex object
            "big_brain": self.big_brain,
            "default_cycle_instruction": self.default_cycle_instruction,
            "cycle_budget": self.cycle_budget,
            "cycles_remaining": self.cycles_remaining,
            "cycle_count": self.cycle_count,
            "metadata": self.metadata,
            "prompt_dictionary": self.prompt_dictionary,
            "project_path": self.project_path,
            "project_url": self.project_url,
            "workspace_path": self.workspace_path,
            "tests_executed": self.tests_executed,
            "cycle_instruction": self.cycle_instruction,
            "track_budget": self.track_budget,
            "left_commands": self.left_commands,
            "max_budget": self.max_budget,
            "container": str(self.container),
        }

    def save_to_file(self, filename):
        # Save object attributes as JSON to a file
        with open(filename, 'w') as file:
            json.dump(self.to_dict(), file, indent=4)

    def think(
        self,
        command_name: CommandName | None,
        command_args: CommandArgs | None,
        agent_thoughts: AgentThoughts | None,
        result: str | None,
        thought_process_id: ThoughtProcessID = "one-shot",
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Runs the agent for one cycle.

        Params:
            instruction: The instruction to put at the end of the prompt.

        Returns:
            The command name and arguments, if any, and the agent's thoughts.
        """
        if "google" in self.config.openai_api_base:
            client = genai.Client(api_key=self.config.openai_api_key)
        else:
            client = OpenAI(api_key=self.config.openai_api_key)

        if not self.config.conversation:
            if self.cycle_count == 0:
                prompt = self.construct_base_prompt()
            else:
                with open(f"tests/{self.project_path}/logs/prompt_history", "r") as patf:
                    prompt = patf.read()
                if self.cycle_count == 1:
                    prompt += "\n\n## Previous Commands\nBelow are commands that you have executed by far, in sequential order."
                prompt += "\n\n==================Command " + str(self.cycle_count) + "==================\nAgent Thoughts: " + str(agent_thoughts.get("thoughts", {})) + "\nCommand name: " + command_name + "\nCommand args: " + str(command_args) + "\n================Command Result================\n" + result
            
            logger.info(
                f"{Fore.GREEN}Creating chat completion with model {self.config.llm_model}{Fore.RESET}"
            )
            response = create_chat_completion(client, self.config.llm_model, prompt)
            self.cycle_count += 1
            with open(f"tests/{self.project_path}/logs/prompt_history", "w") as patf:
                patf.write(prompt)
            return self.on_response(response, thought_process_id, prompt)
        
        if self.cycle_count == 0: # Initial cycle: send guidelines as system instructions
            prompt = self.construct_base_prompt()
            logger.info(
                f"{Fore.GREEN}Starting chat with model {self.config.llm_model}{Fore.RESET}"
            )
            if "google" in self.config.openai_api_base:
                self.chat = client.chats.create(model=self.config.llm_model)
            else:
                self.chat = client.responses.create(model=self.config.llm_model, input=prompt)
                response = self.chat.output_text
        else:
            prompt = self.cycle_instruction + "\n================Previous Command Result================\n" + result
            
        with open(f"tests/{self.project_path}/logs/prompt_history", "a+") as patf:
            patf.write("================================PROMPT " + str(self.cycle_count) + "================================\n" + prompt + "\n\n\n")
        
        logger.info(
            f"{Fore.GREEN}Sending request to model {self.config.llm_model}{Fore.RESET}"
        )
        if "google" in self.config.openai_api_base:
            response = send_message_gemini(self.chat, prompt)
        elif self.cycle_count > 0:
            response = send_message_gpt(self.chat, self.config.llm_model, client, prompt)

        self.cycle_count += 1
        return self.on_response(response, thought_process_id, prompt)
   
    @abstractmethod
    def execute(
        self,
        command_name: str | None,
        command_args: dict[str, str] | None,
        user_input: str | None,
    ) -> str:
        """Executes the given command, if any, and returns the agent's response.

        Params:
            command_name: The name of the command to execute, if any.
            command_args: The arguments to pass to the command, if any.
            user_input: The user's input, if any.

        Returns:
            The results of the command.
        """
        ...


    def construct_base_prompt(
        self
    ) -> str:
        """
        Constructs the base prompt for the agent, including the system prompt,
        the agent's role, and any additional instructions.
        """

        ## added this part to change the prompt structure

        prompt = self.prompt_dictionary["role"]
        
        definitions_prompt = ""
        static_sections_names = ["goals", "commands"]

        for key in static_sections_names:
            if isinstance(self.prompt_dictionary[key], list):
                definitions_prompt += "\n".join(self.prompt_dictionary[key]) + "\n"
            elif isinstance(self.prompt_dictionary[key], str):
                definitions_prompt += self.prompt_dictionary[key] + "\n"
            else:
                raise TypeError("For now we only support list and str types.")
        
        definitions_prompt += "Project github url (in case if you need to clone repo): {}".format(self.project_url)
        
        if self.past_attempt != "":
            definitions_prompt += "\n{}\n".format(self.past_attempt)

        ### Read static prompt files
        gradle_guidelines = files("buildAnaDroid.prompts.prompt_files").joinpath("gradle_guidelines").read_text(encoding="utf-8")

        prompt += definitions_prompt + "\n\n" + gradle_guidelines + "\n\n" + self.cycle_instruction
        return prompt
    

    def on_response(
        self,
        llm_response: str,
        thought_process_id: ThoughtProcessID,
        prompt: str,
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Called upon receiving a response from the chat model.

        Adds the last/newest message in the prompt and the response to `history`,
        and calls `self.parse_and_process_response()` to do the rest.

        Params:
            llm_response: The raw response from the chat model
            prompt: The prompt that was executed
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The parsed command name and command args, if any, and the agent thoughts.
        """

        try:
            return self.parse_and_process_response(
                llm_response, thought_process_id, prompt
            )
        except SyntaxError as e:
            logger.error(f"Response could not be parsed: {e}")
            return None, None, {}


    @abstractmethod
    def parse_and_process_response(
        self,
        llm_response: str,
        thought_process_id: ThoughtProcessID,
        prompt: str,
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Validate, parse & process the LLM's response.

        Must be implemented by derivative classes: no base implementation is provided,
        since the implementation depends on the role of the derivative Agent.

        Params:
            llm_response: The raw response from the chat model
            prompt: The prompt that was executed
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The parsed command name and command args, if any, and the agent thoughts.
        """
        pass

