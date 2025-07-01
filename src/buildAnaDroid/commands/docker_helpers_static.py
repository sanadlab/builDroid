import docker
from docker.errors import ImageNotFound
import os
import subprocess
import time
from buildAnaDroid.logs import logger
import socket
from importlib.resources import files
import re

PROMPT_MARKER = "\r\n__AGENT_SHELL_END_MARKER__$"
SOCKET_RECV_TIMEOUT = 5.0 # Timeout for each individual recv() call
COMMAND_TOTAL_TIMEOUT = 60.0 # Overall timeout for the command to complete

def create_persistent_shell(container):
    """
    Creates a persistent shell session inside the container using Docker's attach API.
    Returns:
        socket: A socket connected to the container's shell.  You'll write commands to this.
    """
    client = docker.from_env()
    exec_id = client.api.exec_create(
        container.id,
        cmd="/bin/bash",
        stdin=True,
        stdout=True,
        stderr=True,
        tty=True,
    )['Id']
    raw_socket = client.api.exec_start(
        exec_id,
        detach=False, # Must be False to get the socket for streaming
        tty=True,
        stream=True,
        socket=True    # Request the underlying socket
    )
    stream_socket = raw_socket._sock if hasattr(raw_socket, '_sock') else raw_socket
    stream_socket.settimeout(5)
    
    interrupted = False
    output_buffer = b""
    while True:
        try:
            # Adjust buffer size as needed; 4096 is common
            chunk = stream_socket.recv(4096)
            if not chunk:
                break
            output_buffer += chunk
            if PROMPT_MARKER.encode('utf-8') in output_buffer:
                break # Command completed and prompt returned
        except socket.timeout:
                interrupted = True
                # No data received within SOCKET_RECV_TIMEOUT. Continue waiting if total timeout not hit.
                logger.debug(f"Socket recv timed out, retrying...")
                continue # Go back to start of loop to check total timeout and try recv again
        except Exception as e:
            print(f"ERROR: Exception during socket recv: {e}")
            break # Exit on other errors
        
    return stream_socket


def close_persistent_shell(socket):
    """Closes the socket connection to the container's shell."""
    try:
        socket._sock.close()
    except Exception as e:
        print(f"Error closing socket: {e}")


def check_image_exists(image_name):
    client = docker.from_env()
    try:
        client.images.get(image_name)
        print(f"Image '{image_name}' exists.")
        return True
    except ImageNotFound:
        print(f"Image '{image_name}' does not exist.")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def build_image(dockerfile_path, tag):
    client = docker.from_env()
    try:
        print(f"Building Docker image from {dockerfile_path} with tag {tag}...")
        image, logs = client.images.build(path=dockerfile_path, dockerfile="Dockerfile", tag=tag, rm=True, nocache=True, platform='linux/amd64')
        return "Docker image built successfully.\n"
    except Exception as e:
        return f"An error occurred while building the Docker image: {e}"
import docker


def start_container(image_tag, name):
    client = docker.from_env()
    subprocess.run(['docker', 'rm', '-vf', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        print(f"Running new container from image {image_tag}...")
        container = client.containers.run(image_tag, detach=True, tty=True, stdin_open=True, name=name)
        print(f"Container {container.short_id} is running.")
        return container
    except Exception as e:
        print(f"An error occurred while running the container: {e}")
        return None


def locate_or_import_gradlew(agent):
    execute_command_in_container(agent.shell_socket, f"cd {agent.project_path}")
    find_cmd = "find . -name gradlew"
    gradlew_path_str = execute_command_in_container(agent.shell_socket, find_cmd)
    if "gradlew" in gradlew_path_str:
        directory, _, _ = gradlew_path_str.partition("/gradlew")
        execute_command_in_container(agent.shell_socket, f"cd {directory}")
        print(f"Found gradlew and cd'd to its directory relative to project root: {directory}")
        return 0
    print(f"gradlew not found in '{agent.project_path}'. Importing...")
    find_cmd_new = "find . -name build.gradle"
    build_gradle_path_str = execute_command_in_container(agent.shell_socket, find_cmd_new)
    if "build.gradle" in build_gradle_path_str:
        directory, _, _ = build_gradle_path_str.partition("/build.gradle")
        execute_command_in_container(agent.shell_socket, f"cd {directory}")
        delimiter = "---END_OF_FILE_CONTENT---"
        gradlew_text = files("buildAnaDroid.files").joinpath("gradlew").read_text(encoding="utf-8")
        command = f"cat <<'{delimiter}' > gradlew\n{gradlew_text}\n{delimiter}"
        execute_command_in_container(agent.shell_socket, command)
        execute_command_in_container(agent.shell_socket, "chmod +x gradlew")
        return 0.
    print(f"build.gradle file not found. {agent.project_path} is not an Android project.")
    return 1


def execute_command_in_container(sock: socket.socket, command: str):    
    """
    Executes a command in the persistent shell.

    Args:
        socket: The socket returned by create_persistent_shell().
        command: The command to execute.
        timeout: How long to wait for command completion without output change.
        wait: The interval to check for process completion.
    Returns:
        str: The output of the command.
    """

    full_command = f"{command.strip()}\n".encode('utf-8')
    sock.sendall(full_command)
    sock.settimeout(SOCKET_RECV_TIMEOUT) # Set a timeout for individual recv calls
    interrupted_by_timeout = False
    
    output_buffer = b""
    start_time = time.time()

    while True:
        try:
            # Adjust buffer size as needed; 4096 is common
            chunk = sock.recv(4096)
            if not chunk:
                # This means the shell (or exec instance) might have exited
                print("WARNING: Socket recv returned no data. Shell might have exited.")
                break
            output_buffer += chunk
            if PROMPT_MARKER.encode('utf-8') in output_buffer:
                break # Command completed and prompt returned
        except socket.timeout:
                if time.time() - start_time > COMMAND_TOTAL_TIMEOUT:
                    logger.warn(f"Total command timeout ({COMMAND_TOTAL_TIMEOUT}s) reached for: '{command.strip()}'. Sending Ctrl+C.")
                    sock.sendall(b'\x03') # CORRECT WAY TO SEND CTRL+C
                    interrupted_by_timeout = True
                    
                    # Give it a short grace period to process Ctrl+C and perhaps return prompt
                    time.sleep(0.5) 
                    # Try to read any immediate output after Ctrl+C, but don't block indefinitely
                    try:
                        chunk_after_ctrlc = sock.recv(4096)
                        if chunk_after_ctrlc:
                            output_buffer += chunk_after_ctrlc
                    except socket.timeout:
                        pass # Expected if Ctrl+C worked cleanly and no immediate output
                    except Exception as e:
                        logger.debug(f"Error reading after Ctrl+C for '{command.strip()}': {e}")
                    break 
                # No data received within SOCKET_RECV_TIMEOUT. Continue waiting if total timeout not hit.
                logger.debug(f"Socket recv timed out, retrying...")
                continue # Go back to start of loop to check total timeout and try recv again
        except Exception as e:
            print(f"ERROR: Exception during socket recv: {e}")
            break # Exit on other errors

    # Decode the full output
    raw_output = output_buffer.decode('utf-8', errors='replace')
    logger.debug("=====================RAW OUTPUT=====================\n"+raw_output)

    output = _clean_output(raw_output, command.strip(), PROMPT_MARKER)

    if interrupted_by_timeout:
        output += "\n[AGENT_INFO: Command likely interrupted due to timeout/hang]"
    return output

def _clean_output(raw_output: str, sent_command_strip: str, prompt_marker: str) -> str:
    """
    Helper function to clean the raw output from the shell.
    Removes initial ANSI escape codes, the echoed command, and the final prompt marker.
    """
    # 1. Remove ANSI escape codes (common at the beginning of TTY output)
    # This regex matches common ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned_output = ansi_escape.sub('', raw_output)

    logger.debug(f"After ANSI escape removal:\n{cleaned_output}")

    # 2. Find the last occurrence of the prompt marker.
    # Everything after this marker is typically what we *don't* want (the new prompt)
    parts = cleaned_output.rpartition(prompt_marker)

    # If the marker isn't found (shouldn't happen if loop exited by it),
    # return the raw output, possibly indicating an issue.
    if not parts[1]: # parts[1] is the separator (prompt_marker)
        logger.warn(f"Prompt marker '{prompt_marker}' not found in CLEANED output. Returning full raw output.")
        return cleaned_output.strip()

    # The part before the *last* prompt marker is what we're interested in.
    output_before_final_prompt = parts[0]
    
    logger.debug(f"Output before final prompt:\n{output_before_final_prompt}")

    # 3. Try to remove the echoed command itself.
    # The shell usually echoes the command you sent, including the newline.
    command_echo_pattern = sent_command_strip + "\r\n\r" # Common echo pattern

    # Attempt to find the last occurrence of the command echo in the output
    # This is still a bit fragile if the command itself outputs the exact echo pattern,
    # but it's the best we can do without more complex PTY parsing.
    last_command_echo_idx = output_before_final_prompt.rfind(command_echo_pattern)

    if last_command_echo_idx != -1:
        # Get everything after the last echoed command
        final_result = output_before_final_prompt[last_command_echo_idx + len(command_echo_pattern):]
    else:
        # If the command echo isn't found, assume the entire content before the prompt is the output.
        # This handles cases where the shell suppresses echo, or if it's the very first prompt.
        logger.debug(f"Command echo '{sent_command_strip}' not found in output for cleaning. Returning content before prompt.")
        final_result = output_before_final_prompt

    # 4. Remove any leading/trailing whitespace, including newlines/carriage returns
    # that might linger from terminal formatting or initial prompt.
    final_result = final_result.strip()

    return final_result

def stop_and_remove(container):
    container.stop()
    container.remove()
    return "Container stopped and removed successfully"
    