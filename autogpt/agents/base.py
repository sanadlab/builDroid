from __future__ import annotations
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pexpect
import time

import re
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, Optional
import json
import os
import subprocess

if TYPE_CHECKING:
    from autogpt.config import AIConfig, Config

    from autogpt.models.command_registry import CommandRegistry

from autogpt.llm.base import ChatModelResponse, ChatSequence, Message
from autogpt.llm.providers.openai import OPEN_AI_CHAT_MODELS, get_openai_command_specs
from autogpt.llm.utils import count_message_tokens, create_chat_completion
from autogpt.logs import logger
from autogpt.memory.message_history import MessageHistory
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

        self.prompt_dictionary = ai_config.construct_full_prompt(config)
        

        ### Read static prompt files
        prompt_files = "./prompt_files"
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

        
        if self.hyperparams["language"].lower() == "python":
            self.prompt_dictionary["general_guidelines"]= self.python_guidelines
        elif self.hyperparams["language"].lower() == "java":
            self.prompt_dictionary["general_guidelines"]= self.java_guidelines
        elif self.hyperparams["language"].lower() == "javascript":
            self.prompt_dictionary["general_guidelines"]= self.javascript_guidelines
        elif self.hyperparams["language"].lower() in ["c", "c++"]:
            self.prompt_dictionary["general_guidelines"]= self.c_guidelines
        
        self.prompt_dictionary["general_guidelines"]  += "\nWhen debugging a problem, if an approach does not work for multiple consecutibe iterations, think of changing your approach of addressing the problem.\n"
        
        #self.prompt_dictionary["general_guidelines"] = ""
        
        """
        The system prompt sets up the AI's personality and explains its goals,
        available resources, and restrictions."""

        llm_name = self.config.smart_llm if self.big_brain else self.config.fast_llm
        self.llm = OPEN_AI_CHAT_MODELS[llm_name]
        """The LLM that the agent uses to think."""

        self.send_token_limit = send_token_limit or self.llm.max_tokens * 3 // 4
        """
        The token limit for prompt construction. Should leave room for the completion;
        defaults to 75% of `llm.max_tokens`.
        """

        self.history = MessageHistory(
            self.llm,
            max_summary_tlength=summary_max_tlength or self.send_token_limit // 6,
        )

        self.project_path = self.hyperparams["project_path"]
        self.project_url = self.hyperparams["project_url"]
        self.language = self.hyperparams["language"]
        self.workspace_path = "execution_agent_workspace"

        self.current_step = "1"
        self.steps_list = ["1", "2", "3", "4", "5", "6", "7"]
        
        with open(os.path.join(prompt_files, "steps_list.json")) as slj:
            self.steps_object = json.load(slj)
        
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
        self.search_results = self.search_documentation()
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
            "language": self.language,
            "workspace_path": self.workspace_path,
            "current_step": self.current_step,
            "steps_list": self.steps_list,
            "steps_object": self.steps_object,
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
            "search_results": self.search_results,
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
                logger.info("REPETITION DETECTED!!!!!!!!!!!!!!!!!!!!222222222222222222222")
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
        instruction: Optional[str] = None,
        thought_process_id: ThoughtProcessID = "one-shot",
    ) -> tuple[CommandName | None, CommandArgs | None, AgentThoughts]:
        """Runs the agent for one cycle.

        Params:
            instruction: The instruction to put at the end of the prompt.

        Returns:
            The command name and arguments, if any, and the agent's thoughts.
        """

        instruction = instruction or self.default_cycle_instruction

        prompt: ChatSequence = self.construct_prompt(instruction, thought_process_id)
        prompt = self.on_before_think(prompt, thought_process_id, instruction)
        
        ## This is a line added by me to save prompts at each step
        self.prompt_text = prompt.dump()
        #logger.info("CURRENT DIRECTORY {}".format(os.getcwd()))
        

        with open(os.path.join("experimental_setups", self.exp_number, "logs", "prompt_history_{}".format(self.project_path.replace("/", ""))), "a+") as patf:
            patf.write(prompt.dump())
        
        with open(os.path.join("experimental_setups", self.exp_number, "logs", "cycles_list_{}".format(self.project_path.replace("/", ""))), "a+") as patf:
            patf.write(self.cycle_type+"\n")
        # handle querying strategy
        # For now, we do not evaluate the external query
        # we just want to observe how good is it
    
        raw_response = create_chat_completion(
            prompt,
            self.config,
            functions=get_openai_command_specs(self.command_registry)
            if self.config.openai_functions
            else None,
        )
        
        try:
            response_dict = extract_dict_from_response(
                raw_response.content
            )
            repetition = self.detect_command_repetition(response_dict)
            if repetition:
                logger.info("REPETITION DETECTED, WARNING CODE RR1")
                logger.info(str(self.handle_command_repitition(response_dict, self.hyperparams["repetition_handling"])))
                prompt.extend([Message("user", self.handle_command_repitition(response_dict, self.hyperparams["repetition_handling"]))])
                new_response = create_chat_completion(
                        prompt,
                        self.config,
                        functions=get_openai_command_specs(self.command_registry)
                        if self.config.openai_functions
                        else None,
                    )
                if self.hyperparams["repetition_handling"] == "TOP3":
                    top3_list = json.loads(new_response.content)
                    for r in top3_list:
                        repetition = self.detect_command_repetition(r)
                        if not repetition:
                            raw_response = Message("assistant", str(r))
                elif self.hyperparams["repetition_handling"] == "RESTRICT":
                    raw_response = new_response
            self.cycle_count += 1

            return self.on_response(raw_response, thought_process_id, prompt, instruction)
        except SyntaxError as e:
            return self.on_response(raw_response, thought_process_id, prompt, instruction)
        
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

    def construct_executed_steps_text(self,):
        text = "# List of Steps to Achieve Your Goals:\n"
        text = "Here is the overall list of steps that you might need to fulfill inorder to achieve your goals:\n"
        for k in self.steps_list:
            text += self.steps_object[k]["static_header"] + self.steps_object[k]["step_line"] + "\n"

        text += "\nBelow is a list of commands that you have executed so far and summary of the result of each command:\n"
        for command, summary in self.commands_and_summary:
            text += command + "\nThe summary of the output of above command: " + str(summary)+"\n\n" 
        return text


    def go_to_next_step(self,):
        step_ind = self.steps_list.index(self.current_step)
        if step_ind < 0:
            raise ValueError("DETECTED IMPOSSIBLE STEP NUMBER.")
        elif step_ind == len(self.steps_list) - 1:
            raise ValueError("END OF STEPS, THERE IS NO NEXT STEP")
        
        self.current_step = self.steps_list[step_ind+1]

    def construct_base_prompt(
        self,
        thought_process_id: ThoughtProcessID,
        prepend_messages: list[Message] = [],
        append_messages: list[Message] = [],
        reserve_tokens: int = 0,
    ) -> ChatSequence:
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

        steps_text = self.construct_executed_steps_text()
         
        prompt = ChatSequence.for_model(
            self.llm.name,
            [Message("system", self.prompt_dictionary["role"])])
        
        definitions_prompt = ""
        static_sections_names = ["goals", "commands", "general_guidelines"]
        for key in static_sections_names:
            if isinstance(self.prompt_dictionary[key], list):
                definitions_prompt += "\n".join(self.prompt_dictionary[key]) + "\n"
            elif isinstance(self.prompt_dictionary[key], str):
                definitions_prompt += self.prompt_dictionary[key] + "\n"
            else:
                raise TypeError("For now we only support list and str types.")
        
        definitions_prompt += "\nProject path: the project under scope has the following path/name within the file system, which you should use when calling the tools: {}".format(self.project_path) + "\n"
        definitions_prompt += "\nProject github url (needed for dockerfile script): {}\n".format(self.project_url)
        
        if os.path.exists("problems_memory/{}".format(self.project_path)):
            with open("problems_memory/{}".format(self.project_path)) as pm:
                previous_memory = pm.read()
            definitions_prompt += "\nFrom previous attempts we learned that: {}\n".format(previous_memory)
        
        if self.found_workflows:
            definitions_prompt += "\nThe following workflow files might contain information on how to setup the project and run test cases. We extracted the most important installation steps found in those workflows and turned them into a bash script. This might be useful later on when building/installing and testing the project:\n"
            for w in self.found_workflows:
                definitions_prompt += "\nWorkflow file: {}\nExtracted installation steps:\n{}\n".format(w, self.workflow_to_script(w))
        
        if self.dockerfiles:
            definitions_prompt += "\nWe found the following dockerfile scripts within the repo. The dockerfile scripts might help you build a suitable docker image for this repository: "+ " ,".join(self.dockerfiles) + "\n"
        
        if self.search_results:
            definitions_prompt += "\nWe searched on google for installing / building {} from source code on Ubuntu/Debian.".format(self.project_path)
            definitions_prompt += "Here is the summary of the top 5 results:\n" + self.search_results + "\n"
        
        
        if self.hyperparams["image"]!="NIL":
            definitions_prompt += "For this particular project, the docker image have been already created and the container have been launched, you can skip steps 1 and 2; You can start directly from step 3 (see the steps list below).\n"
        #definitions_prompt += steps_text + "\n"
        
        if len(self.history) > 2:
            last_command = self.history[-2]
            command_result = self.history[-1]
            last_command_section = "{}\n".format(last_command.content)
            append_messages.append(Message("assistant", last_command_section))
            result_last_command = "The result of executing that last command is:\n {}".format(command_result.content)
            append_messages.append((Message("user", result_last_command)))

        if self.cycle_type == "CMD":
            cycle_instruction = self.cmd_cycle_instruction
            if self.track_budget:
                cycle_instruction += "\n" + "In this conversation you can only have a limited number of calls tools. You have so far consumed {} call and {} left.\n".format(self.max_budget - self.left_commands, self.left_commands) + "\n Consider this limitation, so you repeat the same commands unless it is really necessary, such as for debugging and resolving issues.\n"
            prompt.extend(ChatSequence.for_model(
                self.llm.name,
                [Message("user", definitions_prompt + "\n" + steps_text + "\n\n" + cycle_instruction)] + prepend_messages,
            ))
        
            if append_messages:
                prompt.extend(append_messages)
        else:
            cycle_instruction = self.summary_cycle_instruction
            prompt.extend(ChatSequence.for_model(
                self.llm.name,
                [Message("user", definitions_prompt + "\n" + steps_text + "\n\n" + cycle_instruction+"\n" + command_result.content)]
            ))
        return prompt

    def construct_prompt(
        self,
        cycle_instruction: str,
        thought_process_id: ThoughtProcessID,
    ) -> ChatSequence:
        """Constructs and returns a prompt with the following structure:
        1. System prompt
        2. Message history of the agent, truncated & prepended with running summary as needed
        3. `cycle_instruction`

        Params:
            cycle_instruction: The final instruction for a thinking cycle
        """

        if not cycle_instruction:
            raise ValueError("No instruction given")

        #cycle_instruction_msg = Message("user", cycle_instruction)
        cycle_instruction_tlength = 0
        #count_message_tokens(
        #    cycle_instruction_msg, self.llm.name
        #)

        append_messages: list[Message] = []

        response_format_instr = self.response_format_instruction(thought_process_id)
        #if response_format_instr:
        #s    append_messages.append(Message("user", response_format_instr))

        prompt = self.construct_base_prompt(
            thought_process_id,
            append_messages=append_messages,
            reserve_tokens=cycle_instruction_tlength,
        )

        # ADD user input message ("triggering prompt")
        #prompt.append(cycle_instruction_msg)

        return prompt

    # This can be expanded to support multiple types of (inter)actions within an agent
    def response_format_instruction(self, thought_process_id: ThoughtProcessID) -> str:
        if thought_process_id != "one-shot":
            raise NotImplementedError(f"Unknown thought process '{thought_process_id}'")

        RESPONSE_FORMAT_WITH_COMMAND = """```ts
        interface Response {
            // Express your thoughts based on the information that you have collected so far, the possible steps that you could do next and also your reasoning about fixing the bug in question"
            thoughts: string;
            command: {
                name: string;
                args: Record<string, any>;
            };
        }
        ```
        Here is an example of command call that you can output:
        {
            "thoughts": "I have information about the bug, but I need to run the test cases to understand the bug better.",
            "command": {
                "name": "run_tests",
                "args": {
                "name": "Chart",
                "index": 1
                }
            }
        }
        """

        RESPONSE_FORMAT_WITHOUT_COMMAND = """```ts
        interface Response {
            thoughts: {
                // Thoughts
                text: string;
                reasoning: string;
                // Short markdown-style bullet list that conveys the long-term plan
                plan: string;
                // Constructive self-criticism
                criticism: string;
                // Summary of thoughts to say to the user
                speak: string;
            };
        }
        ```"""

        response_format = re.sub(
            r"\n\s+",
            "\n",
            RESPONSE_FORMAT_WITHOUT_COMMAND
            if self.config.openai_functions
            else RESPONSE_FORMAT_WITH_COMMAND,
        )

        use_functions = self.config.openai_functions and self.command_registry.commands
        return (
            f"Respond strictly with JSON{', and also specify a command to use through a function_call' if use_functions else ''}. "
            "The JSON should be compatible with the TypeScript type `Response` from the following:\n"
            f"{response_format}\n"
        )

    def on_before_think(
        self,
        prompt: ChatSequence,
        thought_process_id: ThoughtProcessID,
        instruction: str,
    ) -> ChatSequence:
        """Called after constructing the prompt but before executing it.

        Calls the `on_planning` hook of any enabled and capable plugins, adding their
        output to the prompt.

        Params:
            instruction: The instruction for the current cycle, also used in constructing the prompt

        Returns:
            The prompt to execute
        """
        current_tokens_used = prompt.token_length
        plugin_count = len(self.config.plugins)
        for i, plugin in enumerate(self.config.plugins):
            if not plugin.can_handle_on_planning():
                continue
            plugin_response = plugin.on_planning(
                self.ai_config.prompt_generator, prompt.raw()
            )
            if not plugin_response or plugin_response == "":
                continue
            message_to_add = Message("system", plugin_response)
            tokens_to_add = count_message_tokens(message_to_add, self.llm.name)
            if current_tokens_used + tokens_to_add > self.send_token_limit:
                logger.debug(f"Plugin response too long, skipping: {plugin_response}")
                logger.debug(f"Plugins remaining at stop: {plugin_count - i}")
                break
            prompt.insert(
                -1, message_to_add
            )  # HACK: assumes cycle instruction to be at the end
            current_tokens_used += tokens_to_add
        return prompt

    def on_response(
        self,
        llm_response: ChatModelResponse,
        thought_process_id: ThoughtProcessID,
        prompt: ChatSequence,
        instruction: str,
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

        # Save assistant reply to message history
        self.history.append(prompt[-1])
        self.history.add(
            "assistant", llm_response.content, "ai_response"
        )  # FIXME: support function calls

        if self.cycle_type != "CMD":
            self.summary_result = json.loads(llm_response.content)
            self.steps_object[self.current_step]["result_of_step"].append(self.summary_result)
            return
        
        try:
            return self.parse_and_process_response(
                llm_response, thought_process_id, prompt, instruction
            )
        except SyntaxError as e:
            logger.error(f"Response could not be parsed: {e}")
            with open("parsing_erros_responses.txt", "a") as pers:
                pers.write(llm_response.content+"\n")
            # TODO: tune this message
            self.history.add(
                "system",
                f"Your response could not be parsed."
                "\n\nRemember to only respond using the specified format above!",
            )
            return None, None, {}

        # TODO: update memory/context

    @abstractmethod
    def parse_and_process_response(
        self,
        llm_response: ChatModelResponse,
        thought_process_id: ThoughtProcessID,
        prompt: ChatSequence,
        instruction: str,
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


def add_history_upto_token_limit(
    prompt: ChatSequence, history: MessageHistory, t_limit: int
) -> list[Message]:
    current_prompt_length = prompt.token_length
    insertion_index = len(prompt)
    limit_reached = False
    trimmed_messages: list[Message] = []
    for cycle in reversed(list(history.per_cycle())):
        messages_to_add = [msg for msg in cycle if msg is not None]
        tokens_to_add = count_message_tokens(messages_to_add, prompt.model.name)
        if current_prompt_length + tokens_to_add > t_limit:
            limit_reached = True

        if not limit_reached:
            # Add the most recent message to the start of the chain,
            #  after the system prompts.
            prompt.insert(insertion_index, *messages_to_add)
            current_prompt_length += tokens_to_add
        else:
            trimmed_messages = messages_to_add + trimmed_messages

    return trimmed_messages