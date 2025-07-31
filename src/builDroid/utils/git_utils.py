import os
import json
import subprocess
import importlib.resources as pkg_resources

def clone_and_set_metadata(project_name, repo_source, image, local_path=False) -> dict:
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
            # Try to clone the repository
            subprocess.run(["git", "clone", "--recursive", repo_source], check=True)
        except subprocess.CalledProcessError as e:
            # If the repository already exists, try to fetch and reset to the latest commit
            repo_dir = os.path.basename(repo_source.rstrip('/')).replace('.git', '')
            if os.path.isdir(repo_dir):
                os.chdir(repo_dir)
                subprocess.run(["git", "fetch", "--all"])
                subprocess.run(["git", "reset", "--hard", "origin/HEAD"])
                os.chdir("..")
            else:
                raise RuntimeError(f"Failed to clone repo: {e}")

    os.chdir(cwd)
    
    metadata = {
        "project_name": project_name,
        "project_url": repo_source,
        "image": image,
        "local_path": local_path,
    }

    return metadata