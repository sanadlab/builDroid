import os
import json
import subprocess
import importlib.resources as pkg_resources

def clone_and_set_metadata(project_name, github_url, image, past_attempt):
    cwd = os.getcwd()

    # Clone the repository
    os.makedirs(f"tests/{project_name}/workspace/", exist_ok=True)
    os.chdir(f"tests/{project_name}/workspace/")
    subprocess.run(["git", "clone", "--recursive", github_url])

    os.chdir(cwd)
    
    metadata = {
        "repetition_handling": "RESTRICT",
        "project_path": project_name,
        "project_url": github_url,
        "budget_control": {
            "name": "NO-TRACK"
        },
        "image": image,
        "past_attempt": past_attempt
    }

    return metadata