from __future__ import annotations
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from colorama import Fore
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, Optional
from google import genai
from google.genai.chats import Chat
import json
import os
import subprocess

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config

    from autogpt.models.command_registry import CommandRegistry

from autogpt.llm.providers.openai import get_model_info
from autogpt.llm.utils import send_request
from autogpt.logs import logger
DEFAULT_TRIGGERING_PROMPT = (
    "Determine exactly one command to use based on the given goals "
    "and the progress you have made so far, "
    "and respond using the JSON schema specified previously:"
)

CommandName = str
CommandArgs = dict[str, str]
AgentThoughts = dict[str, Any]

class BaseAgent(metaclass=ABCMeta):
    """Base class for all Auto-GPT agents."""

    ThoughtProcessID = Literal["one-shot"]

    def __init__(
        self,
        ai_config: AIConfig,
        command_registry: CommandRegistry,
        config: Config,
        chat: Chat,
        java_version: str = "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64",
        big_brain: bool = True,
        default_cycle_instruction: str = DEFAULT_TRIGGERING_PROMPT,
        cycle_budget: Optional[int] = 1,
        experiment_file: str = None
    ):
        self.experiment_file = experiment_file
        self.ai_config = ai_config
        """The AIConfig or "personality" object associated with this agent."""

        self.command_registry = command_registry
        """The registry containing all commands available to the agent."""

        self.java_version = java_version

        self.config = config
        """The applicable application configuration."""

        self.big_brain = big_brain
        """
        Whether this agent uses the configured smart LLM (default) to think,
        as opposed to the configured fast LLM.
        """

        self.default_cycle_instruction = default_cycle_instruction
        """The default instruction passed to the AI for a thinking cycle."""

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
        
        with open(experiment_file) as hper:
            self.hyperparams = json.load(hper)

        ## Newly added experimental
        with open("customize.json") as cfile:
            self.customize = json.load(cfile)

        self.prompt_dictionary = ai_config.construct_full_prompt(config)
        
        ### Read static prompt files
        prompt_files = "./prompt_files"

        llm_name = self.config.llm_model 

        self.llm = get_model_info(llm_name)

        self.project_path = self.hyperparams["project_path"]
        self.project_url = self.hyperparams["project_url"]
        self.workspace_path = "execution_agent_workspace"
        self.keep_container = True if self.hyperparams["keep_container"] == "true" else False
        
        self.tests_executed = False

        with open(os.path.join(prompt_files, "cycle_instruction")) as cit:
            self.cycle_instruction = cit.read()
        
        with open("experimental_setups/experiments_list.txt") as eht:
            self.exp_number = eht.read().splitlines()[-1]

        self.track_budget = True
        self.left_commands = 0
        self.max_budget = -1

        self.container = None

    def to_dict(self):
        return {
            "experiment_file": self.experiment_file,
            "ai_config": str(self.ai_config),  # Assuming this is a complex object
            "command_registry": str(self.command_registry),  # Assuming this is a complex object
            "config": str(self.config),  # Assuming this is a complex object
            "big_brain": self.big_brain,
            "default_cycle_instruction": self.default_cycle_instruction,
            "cycle_budget": self.cycle_budget,
            "cycles_remaining": self.cycles_remaining,
            "cycle_count": self.cycle_count,
            "hyperparams": self.hyperparams,
            "prompt_dictionary": self.prompt_dictionary,
            "llm": str(self.llm),  # Assuming this is a complex object
            "project_path": self.project_path,
            "project_url": self.project_url,
            "workspace_path": self.workspace_path,
            "tests_executed": self.tests_executed,
            "cycle_instruction": self.cycle_instruction,
            "exp_number": self.exp_number,
            "track_budget": self.track_budget,
            "left_commands": self.left_commands,
            "max_budget": self.max_budget,
            "container": str(self.container),
        }

    def save_to_file(self, filename):
        # Save object attributes as JSON to a file
        with open(filename, 'w') as file:
            json.dump(self.to_dict(), file, indent=4)
    
    def create_chat_completion(
        self,
        client,
        prompt
    ) -> str:
        response = client.models.generate_content(
            model=self.config.llm_model, contents=prompt
        )
        return response.text
        
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
        client = genai.Client(api_key=self.config.openai_api_key)
        if not self.config.chat_stream:
            if self.cycle_count == 0:
                prompt = self.construct_base_prompt()
            else:
                with open(os.path.join("experimental_setups", self.exp_number, "logs", "prompt_history_{}".format(self.project_path.replace("/", ""))), "r") as patf:
                    prompt = patf.read()
                if self.cycle_count == 1:
                    prompt += "\n\n## Previous Commands\nBelow are commands that you have executed by far, in sequential order."
                prompt += "\n\n==================Command " + str(self.cycle_count) + "==================\nAgent Thoughts:" + str(agent_thoughts.get("thoughts", {})) + "\n" + command_name + "\n" + str(command_args) + "\n================Command Result================\n" + result
            
            logger.info(
                f"{Fore.GREEN}Creating chat completion with model {self.config.llm_model}, temperature {self.config.temperature}{Fore.RESET}"
            )
            response = self.create_chat_completion(client=client, prompt=prompt)
            self.cycle_count += 1
            with open(os.path.join("experimental_setups", self.exp_number, "logs", "prompt_history_{}".format(self.project_path.replace("/", ""))), "w") as patf:
                patf.write(prompt)
            return self.on_response(response, thought_process_id, prompt)
        
        if self.cycle_count == 0: # Initial cycle: send guidelines as system instructions
            prompt = self.construct_base_prompt()
            logger.info(
                f"{Fore.GREEN}Starting chat with model {self.config.llm_model}, temperature {self.config.temperature}{Fore.RESET}"
            )
            self.chat = client.chats.create(model = self.config.llm_model)
        else:
            prompt = self.cycle_instruction + "\n================Previous Command================\nAgent Thoughts:" + str(agent_thoughts.get("thoughts", {})) + "\n" + command_name + "\n" + str(command_args) + "\n================Command Result================\n" + result
            
        with open(os.path.join("experimental_setups", self.exp_number, "logs", "prompt_history_{}".format(self.project_path.replace("/", ""))), "a+") as patf:
            patf.write("================================PROMPT " + str(self.cycle_count) + "================================\n" + prompt + "\n\n\n")
        
        logger.info(
            f"{Fore.GREEN}Sending request to model {self.config.llm_model}{Fore.RESET}"
        )
        response = send_request(
            prompt,
            self.config,
            stream = True,
            chat = self.chat
        )

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
        
        if os.path.exists("problems_memory/{}".format(self.project_path)):
            with open("problems_memory/{}".format(self.project_path)) as pm:
                previous_memory = pm.read()
            definitions_prompt += "\n{}\n".format(previous_memory)

        gradle_guidelines = ""
        with open("prompt_files/gradle_guidelines") as pgl:
            gradle_guidelines += pgl.read()

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
            with open("parsing_erros_responses.txt", "a") as pers:
                pers.write(llm_response+"\n")
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

