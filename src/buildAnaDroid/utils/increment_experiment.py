import os
import shutil

def new_experiment(project_name):
    os.makedirs(f"buildAnaDroid_tests", exist_ok=True)
    print("Creating experiment folder:", project_name)
    failure_text = ""
    if os.path.isdir(f"buildAnaDroid_tests/{project_name}"):
        if os.path.exists(f"buildAnaDroid_tests/{project_name}/output/FAILURE"):
            with open(f"buildAnaDroid_tests/{project_name}/output/FAILURE", "r") as f:
                failure_text = f.read()
        shutil.rmtree(f"buildAnaDroid_tests/{project_name}")
    os.makedirs(f"buildAnaDroid_tests/{project_name}", exist_ok=True)
    os.makedirs(f"buildAnaDroid_tests/{project_name}/saved_contexts", exist_ok=True)
    os.makedirs(f"buildAnaDroid_tests/{project_name}/output", exist_ok=True)
    return failure_text