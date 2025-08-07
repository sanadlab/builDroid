#!/usr/bin/env python3.10
import argparse
import os
import subprocess
import sys
import importlib.resources
import time
import hashlib
import json
from pathlib import Path

from .utils import api_token_setup, api_token_reset, clone_and_set_metadata, new_experiment, create_results_sheet, run_post_process
from .utils import cleaner

# --- Constants and Configuration ---
# Use the same Python interpreter that is running this script for subprocesses.
PYTHON_EXECUTABLE = sys.executable
# Default value for the number parameter, as in the original script.
DEFAULT_NUM = 40
# Maximum retries for the main execution logic.
MAX_RETRIES = 1
DEV_DEBUG = False # Set to True for development debugging

def extract_project_name(github_url: str) -> str:
    """Extracts the project name from a GitHub URL."""
    return github_url.strip().split('/')[-1]

def setup_docker_config():
    """Initializes an empty Docker configuration file."""
    docker_config_path = Path.home() / ".docker" / "config.json"
    docker_config_path.parent.mkdir(parents=True, exist_ok=True)
    docker_config_path.write_text("{}")

def generate_project_hash(repo_source, local_path):
    """
    Generates a SHA-256 hash representing the state of the project's source files.
    """
    if local_path:
        project_path = repo_source
    else:
        project_path = f"builDroid_workspace/{extract_project_name(repo_source)}"
    # Define which file extensions and specific files to include in the hash
    extensions_to_hash = {'.java', '.kt', '.xml', '.gradle', '.kts', '.pro'}
    specific_files_to_hash = {'gradle.properties', 'gradlew', 'gradlew.bat'}

    hasher = hashlib.sha256()
    
    # Walk through the directory tree in a sorted order to ensure consistency
    for root, dirs, files in sorted(os.walk(project_path)):
        # Exclude common non-source directories
        if 'build' in dirs:
            dirs.remove('build')
        if '.idea' in dirs:
            dirs.remove('.idea')
            
        for filename in sorted(files):
            # Check if the file is one we care about
            is_relevant_ext = any(filename.endswith(ext) for ext in extensions_to_hash)
            is_specific_file = filename in specific_files_to_hash
            
            if is_relevant_ext or is_specific_file:
                file_path = os.path.join(root, filename)
                
                # Add the relative file path to the hash
                # This ensures that file renames/moves are detected
                relative_path = os.path.relpath(file_path, project_path)
                hasher.update(relative_path.encode('utf-8'))
                
                # Add the file content to the hash
                try:
                    with open(file_path, 'rb') as f:
                        while chunk := f.read(8192):
                            hasher.update(chunk)
                except IOError:
                    # Handle cases where a file might be unreadable
                    continue

    return hasher.hexdigest()

def load_cache_from_file(project_name):
    """
    Loads the cache from a file in the project's output directory.
    """
    cache_file = f"builDroid_tests/{project_name}/cache.json"

    if not os.path.exists(cache_file):
        return {}
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_cache_to_file(project_name, cache):
    """
    Saves the cache to a file in the project's output directory.
    """
    cache_file = f"builDroid_tests/{project_name}/cache.json"
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=4)

def update_cache(cache: dict, project_name:str, **kwargs) -> dict:
    """
    Updates the cache with the project key and build result.
    """
    project_folder = os.path.join("builDroid_tests", project_name)
    with open(os.path.join(project_folder, "model_responses"), "r") as f:
        cmd_count = int(f.read().split("Response ")[-1].split("==")[0])
    status = "Succeeded" if os.path.exists(os.path.join(project_folder, "output", "SUCCESS")) else "Failed"
    cache.update(kwargs, cmd_count=cmd_count, status=status)
    return cache

def run_builDroid_with_checks(
    cycle_limit: int,
    conversation: bool,
    debug: bool,
    extract_project: bool,
    override_project: bool,
    metadata: dict,
    keep_container: bool,
    local_path: bool
    ):
    """
    Executes the builDroid module and handles the setup and cleanup of Docker containers.
    """
    
    from builDroid.app.main import run_builDroid

    resource_path: Path = importlib.resources.files('builDroid').joinpath('files', 'ai_settings.yaml')
    ai_settings = resource_path.read_text(encoding='utf-8')

    try:
        run_builDroid(
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
        project_name = metadata["project_name"]
        project_path = metadata["project_url"]
        # Extract the project if specified
        if extract_project:
            if local_path:
                if override_project:
                    print(f"Overriding existing project at: {project_path}")
                    subprocess.run(['rm', '-rf', project_path], check=True)
                    subprocess.run(['docker', 'cp', f'{project_name}:/{project_name}', project_path], check=True)
                else:
                    print(f"Copying project to local path: {project_path}_builDroid")
                    subprocess.run(['rm', '-rf', f"{project_path}_builDroid"], check=True)
                    subprocess.run(['docker', 'cp', f'{project_name}:/{project_name}', f"{project_path}_builDroid"], check=True)
            else:
                if override_project:
                    print(f"Overriding existing project at: builDroid_workspace/{project_name}")
                    subprocess.run(['rm', '-rf', f"builDroid_workspace/{project_name}"], check=True)
                    subprocess.run(['docker', 'cp', f'{project_name}:/{project_name}', f"builDroid_workspace/{project_name}"], check=True)
                else:
                    print(f"Copying project to: builDroid_workspace/{project_name}_builDroid")
                    subprocess.run(['rm', '-rf', f"builDroid_workspace/{project_name}_builDroid"], check=True)
                    subprocess.run(['docker', 'cp', f'{project_name}:/{project_name}', f"builDroid_workspace/{project_name}_builDroid"], check=True)
        if keep_container:
            subprocess.run(["docker", "stop", project_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["docker", "rm", "-vf", project_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "system", "prune", "--volumes", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_with_retries(
    project_name: str,
    cycle_limit: int,
    conversation: bool,
    debug: bool,
    extract_project: bool,
    override_project: bool,
    metadata: dict,
    keep_container: bool,
    user_retry: bool,
    local_path: bool
    ):
    """
    Runs the main logic, handles retries, and performs post-processing.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        print("=" * 70)
        print(f"STARTING ITERATION {attempt}:")
        print(f"PROJECT: {project_name}")
        print("=" * 70)

        if os.path.exists(f"builDroid_tests/{project_name}/output/FAILURE"):
            with open(f"builDroid_tests/{project_name}/output/FAILURE", "r") as f:
                metadata["past_attempt"] = f.read()
        run_builDroid_with_checks(cycle_limit=cycle_limit, conversation=conversation, debug=debug, extract_project=extract_project, override_project=override_project, metadata=metadata, keep_container=keep_container, local_path=local_path)

        # Run post-processing and check the result
        if run_post_process(project_name):
            print(f"Post-process succeeded. The extracted .apk file is in the "
                  f"builDroid_tests/{project_name}/output folder.")
            return # Exit the function on success

        print(f"Attempt {attempt} failed.")

    while user_retry:
        print("=" * 70)
        print("PROMPTING USER FOR ADDITIONAL RETRY:")
        print(f"PROJECT: {project_name}")
        print("=" * 70)
        user_input = input(f"Build failed after {MAX_RETRIES} attempts. Retry? (yes/no): ")
        while True:
            if user_input.startswith("Y") or user_input.startswith("y"):
                run_builDroid_with_checks(cycle_limit=cycle_limit, conversation=conversation, debug=debug, extract_project=extract_project, override_project=override_project, metadata=metadata, keep_container=keep_container, local_path=local_path)
                # Run post-processing and check the result
                if run_post_process(project_name):
                    print(f"Post-process succeeded. The extracted .apk file is in the "
                        f"builDroid_tests/{project_name}/output folder.")
                    return # Exit the function on success
                print(f"User prompted retry failed. Exiting program.")
                return 
            elif user_input.startswith("N") or user_input.startswith("n"):
                return
            else:
                user_input = input(f"Invalid input. Please answer with yes/no. \nBuild failed after {MAX_RETRIES} attempts. Retry? (yes/no): ")


def process_repository(
    repo_source: str,
    cycle_limit: int = DEFAULT_NUM,
    conversation: bool = False,
    extract_project: bool = True,
    override_project: bool = False,
    keep_container: bool = False,
    user_retry: bool = False,
    local_path: bool = False,
    project_name: str = None
    ):
    """Processes a single repository."""

    # Set up API token and increment experiment
    api_token_setup()

    if project_name is None:
        if local_path:
            project_name = repo_source
        else:
            project_name = extract_project_name(repo_source)
            
    print("\n" + "-" * 70)
    print(f"Processing Project: {project_name}")
    if local_path:
        print(f"From Local Path: {repo_source}")
    else:
        print(f"From GitHub URL: {repo_source}")
    print("-" * 70)
    setup_docker_config()

    image = "buildroid:1.0.1"

    # Clone the Github repository and set metadata
    metadata = clone_and_set_metadata(project_name, repo_source, image, local_path)

    project_key = generate_project_hash(repo_source, local_path)
    print(f"Project hash generated: {project_key}")
    cache = load_cache_from_file(project_name)

    if project_key == cache.get('project_key'):
        # Handle cache hit
        print(f"Cache hit for project {project_name}.")
        print("Build result:", cache.get('status'))
        return
    
    debug = False
    start_time = time.time()

    metadata.update({"past_attempt": new_experiment(project_name)})

    # Run the main task with retries
    run_with_retries(project_name=project_name, 
                     cycle_limit=cycle_limit, 
                     conversation=conversation, 
                     debug=debug, 
                     extract_project=extract_project, 
                     override_project=override_project, 
                     keep_container=keep_container, 
                     user_retry=user_retry, 
                     metadata=metadata,
                     local_path=local_path)

    end_time = time.time()
    elapsed_time = end_time - start_time
    # Format start_time and end_time as 'YYYY-MM-DD HH:mm:ss'
    start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
    end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
    update_cache(
        cache,
        project_name=project_name,
        project_key=project_key,
        cycle_limit=cycle_limit,
        conversation=conversation,
        debug=debug,
        extract_project=extract_project,
        override_project=override_project,
        keep_container=keep_container,
        user_retry=user_retry,
        metadata=metadata,
        local_path=local_path,
        start_time=start_time_str,
        end_time=end_time_str,
        elapsed_time=float(f"{elapsed_time:.2f}")
    )
    save_cache_to_file(project_name, cache)

def main():
    """Initialization function."""
    parser = argparse.ArgumentParser(
        description="builDroid agent that experiments on GitHub repositories.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Run on a single repository
  buildroid build https://github.com/user/project

  # Run on a list of repositories from a file
  buildroid build repos.txt

  # Run with conversation mode and 50 iterations, keeping containers
  buildroid build https://github.com/user/project -n 50 -c -k

  # Clean test results
  buildroid clean

For more information on a specific command, use:
  buildroid <command> --help
  e.g., buildroid build --help

"""
    )
    subparsers = parser.add_subparsers(
        dest="command", # This will store the name of the subcommand (e.g., "build", "clean")
        help="Available commands"
    )
    build_parser = subparsers.add_parser(
        "build",
        help="Runs builDroid agent to build project.",
        description="Run the builDroid agent on GitHub repositories.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples for 'build' command:
  build https://github.com/user/project -n 30 --conv
  build repos.txt -k
  build project_folder --local
"""
    )
    build_parser.add_argument(
        "repo_source",
        metavar="REPO_SOURCE",
        default = "",
        help="A single GitHub URL, or a path to a .txt file containing one GitHub URL per line, or a local path to a repository."
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
        "-l", "--local",
        action="store_true",
        help="Build from a local path instead of cloning from GitHub."
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
        "-n", "--no-docker",
        action="store_true",
        help="Skip Docker cleaning. Only cleans test results."
    )
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
            cleaner.clean_workspace(args.no_docker)
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

        if "github.com" in repo_source:
            # Handle the case where input is a single URL string
            print("Processing a single repository URL.")
            process_repository(repo_source=repo_source, cycle_limit=args.num, conversation=args.conv, keep_container=args.keep_container, user_retry=True)
        elif args.local:
            print("Processing a local repository.")
            process_repository(repo_source=repo_source, cycle_limit=args.num, conversation=args.conv, keep_container=args.keep_container, user_retry=True, local_path=True)
        else:
            # Handle the case where the input is a file
            print(f"Processing repositories from file: {repo_source}")
            with open(repo_source, 'r') as f:
                repo_urls = [line.strip() for line in f if line.strip()]
            
            for url in repo_urls:
                process_repository(repo_source=url, cycle_limit=args.num, conversation=args.conv, keep_container=args.keep_container, user_retry=False)
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
