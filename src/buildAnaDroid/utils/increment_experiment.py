import os

def new_experiment(project_name):
    os.makedirs(f"tests", exist_ok=True)
    with open("tests/tests_list.txt", "a+") as expl:
        expl.write(f"{project_name}\n")

    print("Creating experiment folder:", project_name)
    os.makedirs(f"tests/{project_name}", exist_ok=True)
    os.makedirs(f"tests/{project_name}/logs", exist_ok=True)
    os.makedirs(f"tests/{project_name}/responses", exist_ok=True)
    os.makedirs(f"tests/{project_name}/saved_contexts", exist_ok=True)
    os.makedirs(f"tests/{project_name}/output", exist_ok=True)