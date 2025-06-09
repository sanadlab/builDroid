"""Commands to execute code"""

COMMAND_CATEGORY = "execute_code"
COMMAND_CATEGORY_TITLE = "Execute Code"

from buildAnaDroid.commands.docker_helpers_static import execute_command_in_container
from buildAnaDroid.agents.agent import Agent
from buildAnaDroid.models.command_decorator import command

@command(
    "linux_terminal",
    "Executes a Shell Command, non-interactive commands only",
    {
        "command": {
            "type": "string",
            "description": "The command line to execute",
            "required": True,
        }
    },
)
def execute_shell(command: str, agent: Agent) -> str:
    """Execute a shell command and return the output

    Args:
        command (str): The command line to execute

    Returns:
        str: The output of the command
    """

    if "nano " in command:
        return "You cannot execute call nano because it's an interactive command."
    elif "docker " in command:
        if agent.container:
            return "You cannot execute docker commands. You already have access to a running container. If you are facing issues such as missing requirement or need to install a package, you can use linux_terminal to interact with the already running container and install or change whatever you want there. You cannot create another container"
        else:
            return "You cannot execute docker commands. Use the command write_to_file to create a dockerfile script which will automatically build and launch a container. If you are facing build error or issues, you can simplify your dockerfile script to reduce the source of errors"
    elif command.startswith("bash "):
        command = command.replace("bash ", "")
    elif "ls -R" in command:
        return "This command usually returns too much output, hence, it is not allowed."
    
    print(f"Executing command '{command}' in container {agent.container.name}...")
    output = execute_command_in_container(agent.shell_socket, command)
    return output
