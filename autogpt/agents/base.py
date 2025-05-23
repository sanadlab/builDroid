from __future__ import annotations
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pexpect
import time

from colorama import Fore
import re
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, Optional
import google.generativeai as genai
from google.generativeai.generative_models import ChatSession
import json
import os
import subprocess

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config

    from autogpt.models.command_registry import CommandRegistry

from autogpt.llm.base import ChatModelResponse, ChatSequence, Message
from autogpt.llm.providers.openai import OPEN_AI_CHAT_MODELS, get_openai_command_specs, get_model_info
from autogpt.llm.utils import count_message_tokens, send_request
from autogpt.logs import logger
from autogpt.prompts.prompt import DEFAULT_TRIGGERING_PROMPT
from autogpt.json_utils.utilities import extract_dict_from_response
from autogpt.commands.info_collection_static import collect_requirements, infer_requirements, extract_instructions_from_readme
from autogpt.commands.docker_helpers_static import start_container, remove_ansi_escape_sequences, ask_chatgpt
from autogpt.commands.search_documentation import search_install_doc

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
        chat: ChatSession,
        java_version: str = "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64",
        big_brain: bool = True,
        default_cycle_instruction: str = DEFAULT_TRIGGERING_PROMPT,
        cycle_budget: Optional[int] = 1,
        send_token_limit: Optional[int] = None,
        summary_max_tlength: Optional[int] = None,
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
        '''
        with open(os.path.join(prompt_files, "python_guidelines")) as pgl:
            self.python_guidelines = pgl.read()
        with open(os.path.join(prompt_files, "java_guidelines")) as pgl:
            self.java_guidelines = pgl.read()
        with open(os.path.join(prompt_files, "javascript_guidelines")) as pgl:
            self.javascript_guidelines = pgl.read()
        with open(os.path.join(prompt_files, "c_guidelines")) as pgl:
            self.c_guidelines = pgl.read()
        with open(os.path.join(prompt_files, "cpp_guidelines")) as pgl:
            self.cpp_guidelines = pgl.read()
        with open(os.path.join(prompt_files, "rust_guidelines")) as pgl:
            self.rust_guidelines = pgl.read()
        
        with open(os.path.join(prompt_files, "tools_list")) as tls:
            self.prompt_dictionary["commands"] = tls.read()

        if self.customize["LANGUAGE_GUIDELINES"]:
            if self.hyperparams["language"].lower() == "python":
                self.prompt_dictionary["general_guidelines"]= self.python_guidelines
            elif self.hyperparams["language"].lower() == "java":
                self.prompt_dictionary["general_guidelines"]= self.java_guidelines
            elif self.hyperparams["language"].lower() == "javascript":
                self.prompt_dictionary["general_guidelines"]= self.javascript_guidelines
            elif self.hyperparams["language"].lower() in ["c", "c++"]:
                self.prompt_dictionary["general_guidelines"]= self.c_guidelines
        else:
            self.prompt_dictionary["general_guidelines"]= ""
        '''

        #if self.customize["GENERAL_GUIDELINES"]:
        if False:
            self.prompt_dictionary["general_guidelines"] += "When debugging a problem, if an approach does not work for multiple consecutibe iterations, think of changing your approach of addressing the problem. For example, if ./gradlew is not found, try finding the gradlew file and run the command with proper file path."
            
        #self.prompt_dictionary["general_guidelines"] = ""
        
        """
        The system prompt sets up the AI's personality and explains its goals,
        available resources, and restrictions."""

        if self.config.openai_api_base is None:
            llm_name = self.config.smart_llm if self.big_brain else self.config.fast_llm
        else:
            llm_name = self.config.other_llm 
        self.llm = get_model_info(llm_name)

        """The LLM that the agent uses to think."""

        self.send_token_limit = send_token_limit or self.llm.max_tokens * 3 // 4
        """
        The token limit for prompt construction. Should leave room for the completion;
        defaults to 75% of `llm.max_tokens`.
        """

        self.project_path = self.hyperparams["project_path"]
        self.project_url = self.hyperparams["project_url"]
        self.workspace_path = "execution_agent_workspace"
        self.keep_container = True if self.hyperparams["keep_container"] == "TRUE" else False
        
        self.cycle_type = "CMD"
        self.tests_executed = False

        with open(os.path.join(prompt_files, "cycle_instruction")) as cit:
            self.cmd_cycle_instruction = cit.read()

        with open(os.path.join(prompt_files, "summarize_cycle")) as cit:
            self.summary_cycle_instruction = cit.read()
        
        with open("experimental_setups/experiments_list.txt") as eht:
            self.exp_number = eht.read().splitlines()[-1]

        self.track_budget = True
        self.left_commands = 0
        self.max_budget = -1

        self.shell = pexpect.spawnu('/bin/bash')
        self.interact_with_shell("cd {}".format(os.path.join(self.workspace_path, self.project_path)))

        self.commands_and_summary = []
        self.written_files = []

        self.container = None

        if self.hyperparams["image"] != "NIL" and 1 == 0:
            self.container = start_container(self.hyperparams["image"])
            if self.container == None:
                logger.info("ERROR HAPPENED WHILE CREATING THE CONTAINER")
                self.hyperparams["image"] = "NIL"

        self.found_workflows = self.find_workflows(self.project_path)
        #self.search_results = self.search_documentation()
        self.dockerfiles = self.find_dockerfiles()
        self.command_stuck = False


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
            "send_token_limit": self.send_token_limit,
            "project_path": self.project_path,
            "project_url": self.project_url,
            "workspace_path": self.workspace_path,
            "cycle_type": self.cycle_type,
            "tests_executed": self.tests_executed,
            "cmd_cycle_instruction": self.cmd_cycle_instruction,
            "summary_cycle_instruction": self.summary_cycle_instruction,
            "exp_number": self.exp_number,
            "track_budget": self.track_budget,
            "left_commands": self.left_commands,
            "max_budget": self.max_budget,
            "container": str(self.container),  # Assuming this is a complex object
            "found_workflows": self.found_workflows,
            #"search_results": self.search_results,
            "dockerfiles": self.dockerfiles,
        }

    def save_to_file(self, filename):
        # Save object attributes as JSON to a file
        with open(filename, 'w') as file:
            json.dump(self.to_dict(), file, indent=4)

    def workflow_to_script(self, workflow_path):
        system_prompt = "This is the content of a workflow file used to run a test workflow for a repository. I want you to turn the file into a '.sh' script that I can use on my machine to prepare and run tests of that specific repository (the file might contain multiple configurations, I want a simple configuration for linux ubuntu). The workflow might be irrelevant or contain no steps for building and testing. In such case, just mention that the script is not about setting up the project for running tests."

        with open(workflow_path) as wpth:
            query = wpth.read()

        return ask_chatgpt(system_prompt, query)

    def search_documentation(self,):
        if os.path.exists("search_logs/{}".format(self.project_path)):
            with open(os.path.join("search_logs", self.project_path, "{}_build_install_from_source.json".format(self.project_path))) as bifs:
                results = json.load(bifs)
            return json.dumps(results)
        results = search_install_doc(self.project_path)
        return json.dumps(results)

    def find_dockerfiles(self,):
        DOCKERFILE_NAME = "Dockerfile"
        PROJ_DIR = "execution_agent_workspace/{}".format(self.project_path)
        try:
            # Run the find command to locate Dockerfile scripts
            result = subprocess.run(
                ["find", PROJ_DIR, "-name", DOCKERFILE_NAME],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                print(f"Error finding Dockerfiles: {result.stderr}")
                return

            # Process the list of found files
            dockerfiles = result.stdout.splitlines()

            return dockerfiles

        except Exception as e:
            print(f"An error occurred: {e}")
            return []
            
    def find_workflows(self, project_name):
        found_files = []
        WORKFLOW_DIR = "execution_agent_workspace/{}/.github/workflows".format(project_name)
        KEYWORDS = ["test", "build", "linux", "unittest", "integration", "deploy"]
        if not os.path.isdir(WORKFLOW_DIR):
            print(f"The directory {WORKFLOW_DIR} does not exist.")
            return

        print(f"Searching for test-related workflows in {WORKFLOW_DIR}...")

        # Find all YAML workflow files in the .github/workflows directory
        try:
            result = subprocess.run(
                ["find", WORKFLOW_DIR, "-name", "*.yml", "-o", "-name", "*.yaml"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                print(f"Error finding files: {result.stderr}")
                return []

            # Process the list of found files
            workflow_files = result.stdout.splitlines()

            for file in workflow_files:
                # Extract the file name from the full path
                filename = os.path.basename(file).lower()
                # Check if any of the keywords are in the file name
                if any(keyword in filename for keyword in KEYWORDS):
                    found_files.append(file)

        except Exception as e:
            print(f"An error occurred: {e}")

        return found_files


    def remove_progress_bars(self, text):
        try:
            with open("prompt_files/remove_progress_bars") as rpb:
                system_prompt= rpb.read()
            summary = ""
            for i in range(int(len(text)/100000)+1):
                query= "Here is the output of a command that you should clean:\n"+ text[i*100000: (i+1)*100000]
                summary += "\n" + ask_chatgpt(query, system_prompt)
                print("CLEANED 100K CHARACTERS.........")
                print("LEN CLEANED:", len(summary))
        except Exception as e:
            print("ERRRRRROOOOOOOOOOOR IN PROGRESSSSSSSSSS:", e)
        return summary


    def interact_with_shell(self, command):
        try:
            self.shell.sendline(command)
            self.shell.expect("\$ ", timeout=1500)
            self.shell.sendline("pwd")
            self.shell.expect("\$ ", timeout=1500)
        except Exception as e:
            return ("Error happened: {}".format(e), None)
        return remove_ansi_escape_sequences(self.shell.before), remove_ansi_escape_sequences(self.shell.after)

    def validate_command_parsing(self, command_dict):
        with open("commands_interface.json") as cif:
            commands_interface = json.load(cif)

        command_dict = command_dict["command"]
        if command_dict["name"] in list(commands_interface.keys()):
            ref_args = commands_interface[command_dict["name"]]
            if isinstance(command_dict["args"], dict):
                command_args = list(command_dict["args"].keys())
                if set(command_args) == set(ref_args):
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False
        
    def detect_command_repetition(self, ref_cmd):
        #TODO("change this")
        return False
        assistant_outputs = [str(extract_dict_from_response(msg.content)["command"]) for msg in self.history if msg.role == "assistant"]
        with open("assistant_output_from_command_repetition.json", "w") as aocr:
            json.dump(assistant_outputs+[str(ref_cmd["command"])], aocr)
        try:
            if str(ref_cmd["command"]) in assistant_outputs:
                logger.info("REPETITION DETECTED !!! CODE 2")
                return True
            else:
                return False
        except Exception as e:
            with open("exception_files.txt", "w") as ef:
                ef.write(str(e))
            print("Exception raised,", e)
            return False
        
    def handle_command_repitition(self, repeated_command: dict, handling_strategy: str = ""):
        if handling_strategy == "":
            return ""
        elif handling_strategy == "RESTRICT":
            return "Your next command should be totally different from this command: {}".format(repeated_command["command"])
        elif handling_strategy == "TOP3":
            return "Suggest three commands that would make sense to execute given your current input. Give the full json object of each command with all attributes, put the three commands in a list, i.e, [{...}, {...}, {...}]. Do not add any text explanataion before or after the list of the three commands."
        else:
            raise ValueError("The value given to the param handling_strategy is unsuported: {}".format(handling_strategy))

    def think(
        self,
        command_name: CommandName | None,
        command_args: CommandArgs | None,
        result: str | None,
        thought_process_id: ThoughtProcessID = "one-shot",
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Runs the agent for one cycle.

        Params:
            instruction: The instruction to put at the end of the prompt.

        Returns:
            The command name and arguments, if any, and the agent's thoughts.
        """
        if self.cycle_count == 0: # Initial cycle: send guidelines as system instructions
            prompt = self.construct_base_prompt()
            genai.configure(api_key=self.config.openai_api_key)
            model = genai.GenerativeModel(self.config.other_llm)
            self.chat = model.start_chat(history=[])
            logger.info(
                f"{Fore.GREEN}Starting chat with model {self.config.other_llm}, temperature {self.config.temperature}{Fore.RESET}"
            )
        else:
            prompt = self.cmd_cycle_instruction + "\n================Previous Command================\n" + command_name + "\n" + str(command_args) + "\n================Command Result================\n" + result
            
        with open(os.path.join("experimental_setups", self.exp_number, "logs", "prompt_history_{}".format(self.project_path.replace("/", ""))), "a+") as patf:
            patf.write("\n\n\n" + prompt)
        
        logger.info(
            f"{Fore.GREEN}Sending request to model {self.config.other_llm}{Fore.RESET}"
        )
        response = send_request(
            prompt,
            self.config,
            stream = True,
            chat = self.chat,
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
        self,
        thought_process_id: ThoughtProcessID = "one-shot",
        prepend_messages: list[Message] = [],
        append_messages: list[Message] = [],
        reserve_tokens: int = 0,
    ) -> str:
        """Constructs and returns a prompt with the following structure:
        1. System prompt
        2. `prepend_messages`
        3. Message history of the agent, truncated & prepended with running summary as needed
        4. `append_messages`

        Params:
            prepend_messages: Messages to insert between the system prompt and message history
            append_messages: Messages to insert after the message history
            reserve_tokens: Number of tokens to reserve for content that is added later
        """

        ## added this part to change the prompt structure

        prompt = self.prompt_dictionary["role"]
        
        definitions_prompt = ""
        static_sections_names = ["goals", "commands", "general_guidelines"]

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
            definitions_prompt += "\nFrom previous attempts we learned that: {}\n".format(previous_memory)

        gradle_guidelines = ""
        with open("prompt_files/gradle_guidelines") as pgl:
            gradle_guidelines += pgl.read()

        prompt += definitions_prompt + "\n\n" + self.cmd_cycle_instruction + "\n\n" + gradle_guidelines
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

