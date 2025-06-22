import shutil
import os
from pathlib import Path

# List of directories to be completely removed and recreated by --clean.
DIRECTORIES_TO_CLEAN = ["logs", "tests"]

def clean_workspace():
    """
    Handles the --clean operation.
    Completely removes and recreates the specified directories.
    """
    print("--- Cleaning workspace ---")
    for dir_name in DIRECTORIES_TO_CLEAN:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"Removing directory tree: {dir_path}")
            # Use shutil.rmtree to remove the directory and all its contents
            shutil.rmtree(dir_path, ignore_errors=True)
        else:
            print(f"Directory '{dir_path}' not found, skipping removal.")
    print("--- Workspace cleaned successfully. ---")
    add = input("\nADDITIONAL PROMPT: Clean Docker resources? (Yes/No): ").strip()
    if add.startswith("y") or add.startswith("Y"):
        clean_docker_resources()

import subprocess
import sys

def clean_docker_resources():
    """
    Prompts the user to choose between cleaning Docker containers only
    or all Docker resources (containers, images, volumes, networks),
    then performs the chosen action after a confirmation.
    """

    action = ""
    # Prompt user to choose action
    while action not in ["containers", "all"]:
        print("\nChoose an action:")
        print("  1) Stop and remove all Docker containers and volumes only.")
        print("  2) Stop and remove all Docker containers, images, volumes, and networks.")
        print("  3) Cancel cleaning and keep all Docker containers.")
        choice = input("Enter option: ").strip()

        if choice == "1":
            action = "containers"
        elif choice == "2":
            action = "all"
        elif choice == "3":
            print("Cleaning cancelled. Exiting.")
            return
        else:
            print("Invalid choice. Please enter '1' or '2'.")

    try:
        # Get IDs of all running containers
        result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, check=True)
        container_ids = result.stdout.strip().splitlines()

        if container_ids:
            print("Stopping running containers...")
            subprocess.run(["docker", "kill"] + container_ids, check=True)

        if action == "containers":
            print("Removing all stopped containers and volumes...")
            subprocess.run(["docker", "container", "prune", "-f"], check=True)
            subprocess.run(["docker", "system", "prune", "--volumes", "-f"], check=True)
            print("Removed all containers and volumes.")

        elif action == "all":
            print("Pruning all Docker system resources (containers, images, volumes, networks)...")
            subprocess.run(["docker", "system", "prune", "-a", "--volumes", "-f"], check=True)
            print("Removed all containers, images, volumes, and networks.")

    except FileNotFoundError:
        print("\nError: 'docker' command not found.")
        print("Please ensure Docker Desktop/Engine is installed and 'docker' is in your system's PATH.")
        return
    except subprocess.CalledProcessError as e:
        print(f"\nError executing Docker command (exit code {e.returncode}):")
        print(f"Command: {' '.join(e.cmd)}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return

    print("\nOperation complete.")
