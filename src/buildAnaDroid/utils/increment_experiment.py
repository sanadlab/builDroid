import os
import shutil

def new_experiment(project_name):
    os.makedirs(f"tests", exist_ok=True)
    with open("tests/tests_list.txt", "a+") as expl:
        expl.write(f"{project_name}\n")

    print("Creating experiment folder:", project_name)
    failure_text = ""
    if os.path.isdir(f"tests/{project_name}"):
        if os.path.exists(f"tests/{project_name}/output/FAILURE"):
            with open(f"tests/{project_name}/output/FAILURE", "r") as f:
                failure_text = f.read()
        shutil.rmtree(f"tests/{project_name}")
    os.makedirs(f"tests/{project_name}", exist_ok=True)
    os.makedirs(f"tests/{project_name}/logs", exist_ok=True)
    os.makedirs(f"tests/{project_name}/responses", exist_ok=True)
    os.makedirs(f"tests/{project_name}/saved_contexts", exist_ok=True)
    os.makedirs(f"tests/{project_name}/output", exist_ok=True)
    return failure_text