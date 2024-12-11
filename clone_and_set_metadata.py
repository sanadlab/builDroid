import os
import json
import sys
import subprocess

def clone_repository(github_url, project_name):

    cwd = os.getcwd()
    # Clone the repository

    os.chdir("execution_agent_workspace/")
    subprocess.run(["git", "clone", github_url])
    #print("project cloned 999999999999999")
    # Define project directory
    project_directory = os.path.join(os.getcwd(), project_name)

    os.chdir(cwd)
    return project_directory

def create_metadata_file(project_name, github_url, language, image):
    # Define metadata dictionary
    metadata = {
        "repetition_handling": "RESTRICT",
        "project_path": project_name,
        "project_url": github_url,
        "budget_control": {
            "name": "NO-TRACK"
        },
        "language": language,
        "image": image
    }

    # Define metadata file path
    metadata_file = "project_meta_data.json"

    # Write metadata to file
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=4)

    print(f"Metadata file created: {metadata_file}")

if __name__ == "__main__":
    # Check if correct number of arguments are provided
    if len(sys.argv) != 4:
        print("Usage: python my_script.py project_name github_url language")
        sys.exit(1)

    project_name = sys.argv[1]
    github_url = sys.argv[2]
    language = sys.argv[3]
    image = project_name+"_image:ExecutionAgent"

    # Clone repository
    project_directory = clone_repository(github_url, project_name)

    # Create metadata file
    create_metadata_file(project_name, github_url, language, image)
