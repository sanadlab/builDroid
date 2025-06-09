import docker
from docker.errors import ImageNotFound
import os
import subprocess
import time
from buildAnaDroid.logs import logger
import socket

def create_persistent_shell(container):
    """
    Creates a persistent shell session inside the container using Docker's attach API.
    Returns:
        socket: A socket connected to the container's shell.  You'll write commands to this.
    """
    client = docker.from_env()
    exec_id = client.api.exec_create(
        container.id,
        cmd="/bin/sh",
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
        image, logs = client.images.build(path=dockerfile_path, dockerfile="Dockerfile", tag=tag, rm=True, nocache=True)
        return "Docker image built successfully.\n"
    except Exception as e:
        return f"An error occurred while building the Docker image: {e}"
import docker


def start_container(image_tag, name):
    client = docker.from_env()
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
        return
    print(f"gradlew not found in '{agent.project_path}'. Importing...")
    container_gradlew_dest = os.path.join(agent.project_path, 'gradlew')
    subprocess.run(['docker', 'cp', f'scripts/gradlew', f'{agent.container.id}:/{container_gradlew_dest}'])
    execute_command_in_container(agent.shell_socket, "chmod +x gradlew")
    return


def execute_command_in_container(socket: socket, command: str):    
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
    full_command = f"{command.strip()}\n"
    socket.sendall(full_command.encode('utf-8'))
    output_buffer = b""
    interrupted = False
    time.sleep(0.2) # Small delay for shell to process
    
    while True:
        try:
            # Adjust buffer size as needed; 4096 is common
            chunk = socket.recv(4096)
            if not chunk:
                # This means the shell (or exec instance) might have exited
                print("WARNING: Socket recv returned no data. Shell might have exited.")
                break
            output_buffer += chunk
            # Check if the marker is in the decoded buffer
            # Decode carefully, marker might be split across chunks in rare cases
            # For simplicity, we decode the whole buffer each time.
            if "#".encode('utf-8') in output_buffer:
                break
        except BlockingIOError: # Should not happen if settimeout is used, but good practice
            print(f"WARNING: BlockingIOError for '{command}'. Attempting to interrupt with Ctrl+C.")
            # Handle as appropriate, perhaps like timeout
            interrupted = True # Treat as an issue
            socket.sendall(b'\x03') # Send ETX (Ctrl+C)
            # Give it a very short moment to see if Ctrl+C produced output or our marker
            time.sleep(0.2)
            # Try one more small read to catch any immediate post-Ctrl+C output or the marker
            try:
                chunk = socket.recv(1024) # Don't block for long here
                if chunk: output_buffer += chunk
            except BlockingIOError: # Expected if Ctrl+C worked cleanly
                pass
            except Exception: # Other socket errors after Ctrl+C
                pass
            break
        except Exception as e:
            print(f"ERROR: Exception during socket recv: {e}")
            break # Exit on other errors

    # Decode the full output
    full_output_str = output_buffer.decode('utf-8', errors='replace')
    logger.debug("=====================FULL OUTPUT=====================\n"+full_output_str)
    _, _, output = full_output_str.partition(command)
    final_output, _, _ = output.partition("#")
    final_output = final_output.strip()
    if interrupted:
        final_output += "\n[AGENT_INFO: Command likely interrupted due to timeout/hang]"
    return final_output


def stop_and_remove(container):
    container.stop()
    container.remove()
    return "Container stopped and removed successfully"
    