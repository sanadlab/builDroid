import os
import pandas as pd

# Path to the "saved_contexts" directory
saved_contexts_path = "experimental_setups/experiment_2/saved_contexts"

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
df.to_excel("cmd_counts_with_status.xlsx", index=False)

print("Spreadsheet 'cmd_counts_with_status.xlsx' created.")
