import os
import json
import subprocess
import importlib.resources as pkg_resources

def clone_and_set_metadata(project_name, repo_source, image, past_attempt, local_path=False):
    cwd = os.getcwd()

    # If a local path is provided, use it instead of cloning
    if local_path:
        if not os.path.exists(repo_source):
            raise FileNotFoundError(f"Local path '{repo_source}' does not exist.")
    else:
        # Clone the repository from GitHub
        os.makedirs(f"builDroid_workspace", exist_ok=True)
        os.chdir(f"builDroid_workspace")
        try:
            subprocess.run(["git", "clone", "--recursive", repo_source])
        except Exception as e:
            raise RuntimeError(f"Failed to clone repository: {e}")

    os.chdir(cwd)
    
    metadata = {
        "repetition_handling": "RESTRICT",
        "project_name": project_name,
        "project_url": repo_source,
        "budget_control": {
            "name": "NO-TRACK"
        },
        "image": image,
        "past_attempt": past_attempt,
        "local_path": local_path,
    }

    return metadata