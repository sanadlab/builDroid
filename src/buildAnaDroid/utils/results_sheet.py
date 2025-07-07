import os
import pandas as pd
def create_results_sheet():
    # Result data
    data = []

    # Loop through each project folder
    for project_folder in os.listdir("buildAnaDroid_tests"):
        project_name = os.path.join("buildAnaDroid_tests", project_folder)
        if os.path.isdir(project_name):
            cmd_count = 0
            status = "Succeeded" if os.path.exists(os.path.join(project_name, "saved_contexts", "SUCCESS")) else "Failed"

            # Loop through cycle_* files
            for file in os.listdir(os.path.join(project_name, "saved_contexts")):
                if file.startswith("cycle_"):
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
