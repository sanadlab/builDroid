import os
import pandas as pd

# Read the last line of experiments_list.txt
experiments_file = "experimental_setups/experiments_list.txt"
if not os.path.exists(experiments_file):
    print(f"Error: {experiments_file} does not exist.")
    exit(1)

with open(experiments_file, 'r') as f:
    lines = f.readlines()
    if not lines:
        print(f"Error: {experiments_file} is empty.")
        exit(1)
    last_line = lines[-1].strip()

# Path to the "saved_contexts" directory
saved_contexts_path = f"experimental_setups/{last_line}/saved_contexts"

# Result data
data = []

# Loop through each project folder
for project_folder in os.listdir(saved_contexts_path):
    project_path = os.path.join(saved_contexts_path, project_folder)
    if os.path.isdir(project_path):
        cmd_count = 0
        status = "Succeeded" if os.path.exists(os.path.join(project_path, "SUCCESS")) else "Failed"

        # Loop through cycle_* files
        for file in os.listdir(project_path):
            if file.startswith("cycle_") and os.path.exists(os.path.join(project_path, file)):
                with open(os.path.join(project_path, file), 'r', encoding='utf-8') as f:
                    cmd_count += 1

        # Append result
        data.append({
            "Project Name": project_folder,
            "CMD Count": cmd_count,
            "Status": status
        })

# Convert to DataFrame and export
df = pd.DataFrame(data)
df.sort_values(by="Project Name", inplace=True)
df.to_excel("experiment_results.xlsx", index=False)

print("Spreadsheet 'experiment_results.xlsx' created.")
