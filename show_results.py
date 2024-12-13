import os
import sys

def get_highest_numbered_file(directory, prefix):
    """Get the file with the highest number at the end of its name for a given prefix."""
    files = [f for f in os.listdir(directory) if f.startswith(prefix) and f[len(prefix):].isdigit()]
    if not files:
        return None
    highest_file = max(files, key=lambda x: int(x[len(prefix):]))
    return highest_file

def main():
    if len(sys.argv) != 2:
        print("Usage: python show_results.py <project_name>")
        sys.exit(1)

    project_name = sys.argv[1]

    # Read the last line of experiments_list.txt
    experiments_file = "experimental_setups/experiments_list.txt"
    if not os.path.exists(experiments_file):
        print(f"Error: {experiments_file} does not exist.")
        sys.exit(1)

    with open(experiments_file, 'r') as f:
        lines = f.readlines()
        if not lines:
            print(f"Error: {experiments_file} is empty.")
            sys.exit(1)
        last_line = lines[-1].strip()

    # Build the files directory path
    files_dir = f"experimental_setups/{last_line}/files/{project_name}"
    if not os.path.exists(files_dir):
        print(f"Error: {files_dir} does not exist.")
        sys.exit(1)

    # Get the highest-numbered Dockerfile
    dockerfile = get_highest_numbered_file(files_dir, "Dockerfile_")
    if dockerfile:
        dockerfile_path = os.path.join(files_dir, dockerfile)
        print("="*70)
        print(f"Latest docker file Dockerfile: {dockerfile_path}")
        print("="*70)
        with open(dockerfile_path, 'r') as f:
            print(f.read())
    else:
        print("No Dockerfile found.")

    # Get the highest-numbered SETUP_AND_INSTALL.sh
    setup_file = get_highest_numbered_file(files_dir, "SETUP_AND_INSTALL.sh_")
    if setup_file:
        setup_file_path = os.path.join(files_dir, setup_file)
        print("="*70)
        print(f"Latest installation script SETUP_AND_INSTALL.sh: {setup_file_path}")
        print("="*70)
        with open(setup_file_path, 'r') as f:
            print(f.read())
    else:
        print("No SETUP_AND_INSTALL.sh file found.")

    # Check for SUCCESS file in saved_contexts directory
    success_file = f"experimental_setups/{last_line}/saved_contexts/{project_name}/SUCCESS"
    if os.path.exists(success_file):
        print("="*70)
        print("SUCCESS")
    else:
        print("="*70)
        print("FAILED")

if __name__ == "__main__":
    main()
