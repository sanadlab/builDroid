#!/usr/bin/env python3.10
import argparse
import os
import subprocess
import sys
import importlib.resources
from pathlib import Path

from .utils import api_token_setup, api_token_reset, clone_and_set_metadata, new_experiment, create_results_sheet, run_post_process, check_requirements
from .utils import cleaner

# --- Constants and Configuration ---
# Use the same Python interpreter that is running this script for subprocesses.
PYTHON_EXECUTABLE = sys.executable
# Default value for the number parameter, as in the original script.
DEFAULT_NUM = 30
# Maximum retries for the main execution logic.
MAX_RETRIES = 2
DEV_DEBUG = False # Set to True for development debugging

def extract_project_name(github_url: str) -> str:
    """Extracts the project name from a GitHub URL."""
    return github_url.strip().split('/')[-1]

def setup_docker_config():
    """Initializes an empty Docker configuration file."""
    docker_config_path = Path.home() / ".docker" / "config.json"
    docker_config_path.parent.mkdir(parents=True, exist_ok=True)
    docker_config_path.write_text("{}")


def run_buildAnaDroid_with_checks(cycle_limit: int, conversation: bool, debug: bool, metadata: dict, keep_container: bool):
    """
    This function replaces the logic of `run.sh`.
    It checks/installs requirements and then executes the buildAnaDroid module.
    """
    # 1. Check requirements (replaces `scripts/check_requirements.py`)
    if check_requirements():
        print("Installing missing packages from requirements.txt...")
        subprocess.run([PYTHON_EXECUTABLE, "-m", "pip", "install", "-r", "requirements.txt"])
    print("All requirements are met.")

    # 2. Run the run_buildAnaDroid function
    from buildAnaDroid.app.main import run_buildAnaDroid

    resource_path: Path = importlib.resources.files('buildAnaDroid').joinpath('files', 'ai_settings.yaml')
    ai_settings = resource_path.read_text(encoding='utf-8')

    try:
        run_buildAnaDroid(
            cycle_limit=cycle_limit,
            ai_settings=ai_settings,
            debug=debug,
            conversation=conversation,
            working_directory=Path(
                __file__
            ).parent.parent.parent,
            metadata=metadata
        )
    finally:
        if keep_container:
            subprocess.run(["docker", "stop", metadata["project_path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["docker", "rm", "-vf", metadata["project_path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "system", "prune", "--volumes", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_with_retries(project_name: str, num: int, conversation: bool, debug:bool, metadata: dict, keep_container:bool, user_retry:bool):
    """
    Runs the main logic, handles retries, and performs post-processing.
    This replaces the `run_with_retries` function from the shell script.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        print("=" * 70)
        print(f"STARTING ITERATION {attempt}:")
        print(f"PROJECT: {project_name}")
        print("=" * 70)

        if os.path.exists(f"tests/{project_name}/output/FAILURE"):
            with open(f"tests/{project_name}/output/FAILURE", "r") as f:
                metadata["past_attempt"] = f.read()
        
        # This call now encapsulates the entire logic of `run.sh`
        run_buildAnaDroid_with_checks(num, conversation, debug, metadata, keep_container)

        # Run post-processing and check the result
        if run_post_process(project_name):
            print(f"Post-process succeeded. The extracted .apk file is in the "
                  f"tests/{project_name}/output folder.")
            return # Exit the function on success

        print(f"Attempt {attempt} failed. Retrying...")

    while user_retry:
        print("=" * 70)
        print("PROMPTING USER FOR ADDITIONAL RETRY:")
        print(f"PROJECT: {project_name}")
        print("=" * 70)
        user_input = input(f"Build failed after {MAX_RETRIES} attempts. Retry? (yes/no): ")
        while True:
            if user_input.startswith("Y") or user_input.startswith("Y"):
                run_buildAnaDroid_with_checks(num, conversation, debug, metadata, keep_container)
                # Run post-processing and check the result
                if run_post_process(project_name):
                    print(f"Post-process succeeded. The extracted .apk file is in the "
                        f"tests/{project_name}/output folder.")
                    return # Exit the function on success
            elif user_input.startswith("N") or user_input.startswith("n"):
                return
            else:
                user_input = input(f"Invalid input. Please answer with yes/no. \nBuild failed after {MAX_RETRIES} attempts. Retry? (yes/no): ")

        print(f"User prompted retry failed. Exiting program.")

def process_repository(github_url: str, num: int, conversation: bool, keep_container:bool, user_retry:bool):
    """Processes a single repository."""
    project_name = extract_project_name(github_url)
    print("\n" + "-" * 70)
    print(f"Processing Project: {project_name}")
    print(f"From GitHub URL: {github_url}")
    print("-" * 70)
    past_attempt = new_experiment(project_name)

    setup_docker_config()

    image = "build-anadroid:0.4.4"

    # Clone the Github repository and set metadata
    metadata = clone_and_set_metadata(project_name, github_url, image, past_attempt)

    debug = False

    # Run the main task with retries
    run_with_retries(project_name, num, conversation, debug, metadata, keep_container, user_retry)

def main():
    """Initialization function."""
    parser = argparse.ArgumentParser(
        description="buildAnaDroid agent that experiments on GitHub repositories.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Run on a single repository
  build-anadroid build https://github.com/user/project

  # Run on a list of repositories from a file
  build-anadroid build repos.txt

  # Run with conversation mode and 50 iterations, keeping containers
  build-anadroid build https://github.com/user/project -n 50 -c -k

  # Clean test results
  build-anadroid clean

For more information on a specific command, use:
  build-anadroid <command> --help
  e.g., build-anadroid build --help

"""
    )
    subparsers = parser.add_subparsers(
        dest="command", # This will store the name of the subcommand (e.g., "build", "clean")
        help="Available commands"
    )
    build_parser = subparsers.add_parser(
        "build",
        help="Runs buildAnaDroid agent to build project.",
        description="Run the buildAnaDroid agent on GitHub repositories.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples for 'build' command:
  build https://github.com/user/project -n 30 --conv
  build repos.txt -k
"""
    )
    build_parser.add_argument(
        "repo_source",
        metavar="REPO_SOURCE",
        default = "",
        help="A single GitHub URL, or a path to a file containing one GitHub URL per line."
    )
    build_parser.add_argument(
        "-n", "--num",
        type=int,
        default=DEFAULT_NUM,
        help=f"The cycle limit for the agent. Default: {DEFAULT_NUM}"
    )
    build_parser.add_argument(
        "-c", "--conv",
        action="store_true",
        help="Enable conversation mode."
    )
    build_parser.add_argument(
        "-k", "--keep-container",
        action="store_true",
        help="Keeps container after build. (By default, containers are removed)."
    )
    clean_parser = subparsers.add_parser(
        "clean",
        help="Clean test results and/or Docker resources.",
        description="Clean test results and/or Docker resources.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples for 'clean' command:
  clean                    # Cleans test results and prompts for Docker clean type.
  clean -d                 # Cleans Docker resources and keep test results.
"""
    )
    clean_group = clean_parser.add_mutually_exclusive_group()
    clean_group.add_argument(
        "-d", "--docker",
        action="store_true",
        help="Remove Docker resources (only containers or all resources)"
    )
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
        
    # If command is clean, clean and exit immediately.
    if args.command == "clean":
        if not args.docker:
            cleaner.clean_workspace()
        else:
            cleaner.clean_docker_resources()
        print("Exiting after cleaning.")
        sys.exit(0)

    elif args.command == "build":
        if DEV_DEBUG:
            import debugpy
            debugpy.listen(("0.0.0.0", 5678))
            
            print("Waiting for debugger to attach...")
            # This line will pause your script's execution until you attach the VS Code debugger.
            debugpy.wait_for_client()
            print("Debugger attached!")
        repo_source = str(args.repo_source)

        # Set up API token and increment experiment
        api_token_setup()
        if "github.com" in repo_source:
            # Handle the case where input is a single URL string
            print("Processing a single repository URL.")
            project_name = extract_project_name(repo_source)
            process_repository(args.repo_source, args.num, args.conv, args.keep_container, True)
        else:
            # Handle the case where the input is a file
            print(f"Processing repositories from file: {repo_source}")
            with open(repo_source, 'r') as f:
                repo_urls = [line.strip() for line in f if line.strip()]
            
            for url in repo_urls:
                project_name = extract_project_name(url)
                process_repository(url, args.num, args.conv, args.keep_container, False)
            
            # Generate the final results sheet after all repos are processed
            create_results_sheet()
        api_token_reset()
        print("Execution finished.")

if __name__ == "__main__":
    # Check if we're running with Python 3.10+
    if sys.version_info < (3, 10):
        print("Error: Python 3.10 or higher is required to run this script.")
        sys.exit(1)
    main()
