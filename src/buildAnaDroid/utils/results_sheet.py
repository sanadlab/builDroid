import os
import pandas as pd
import json

def create_results_sheet():
    # --- 1. Define the error structure and create unique internal column names ---
    error_structure = {
        "Process Issue": ["MISSING_LOCAL_PROPERTIES", "MISSING_KEYSTORE", "MISSING_GRADLE_WRAPPER", "NON_DEFAULT_BUILD_COMMAND", "General"],
        "Environment Issue": ["GRADLE_BUILD_SYSTEM", "GRADLE_VERSION", "GRADLE_JDK_MISMATCH", "JAVA_KOTLIN_MISMATCH", "JDK_VERSION", "ANDROID_SDK_VERSION", "MISSING_NDK", "NO_DISK_SPACE", "MISSING_DEPENDENCY", "General"],
        "Project Issue": ["CONFIG_VERSION_CONFLICT", "COMPILATION_ERROR", "General"]
    }

    # Create a list of unique internal column names for specific issues
    # e.g., 'MISSING_KEYSTORE', 'Process Issue_General', 'Environment Issue_General'
    flat_specific_issue_columns = []
    for category, issues in error_structure.items():
        for issue in issues:
            if issue == "General":
                # Create a unique name by prefixing the category
                flat_specific_issue_columns.append(f"{category}_General")
            else:
                flat_specific_issue_columns.append(issue)

    # All high-level category columns
    category_columns = list(error_structure.keys())

    # Final list to store data for each project row
    data = []

    # --- 2. Loop through each project folder ---
    for project_name in os.listdir("builDroid_tests"):
        if project_name == "logs" or not os.path.isdir(os.path.join("builDroid_tests", project_name)):
            continue

        project_folder = os.path.join("builDroid_tests", project_name)

        # Basic project info
        cmd_count = sum(1 for file in os.listdir(os.path.join(project_folder, "saved_contexts")) if file.startswith("cycle_"))
        status = "Succeeded" if os.path.exists(os.path.join(project_folder, "saved_contexts", "SUCCESS")) else "Failed"
        with open(os.path.join(project_folder, "output", "elapsed_time.txt"), "r") as f:
            elapsed_time = float(f.read().strip())
        
        project_data_row = {
            "Project Name": project_name,
            "CMD Count": cmd_count,
            "Status": status,
            "Elapsed Time": elapsed_time
        }

        # Load the error summary JSON
        error_summary_path = os.path.join(project_folder, "output", "error_summary.json")
        if os.path.exists(error_summary_path):
            with open(error_summary_path, "r") as f:
                error_summary = json.load(f)
        else:
            error_summary = {cat: {iss: 0 for iss in issues} for cat, issues in error_structure.items()}
            error_summary["Unknown"] = 0

        # --- 3. Flatten the JSON using the unique internal column names ---
        total_project_errors = 0
        
        for category, specific_issues in error_structure.items():
            category_sum = 0
            for issue in specific_issues:
                # Determine the unique column name
                column_name = issue
                if issue == "General":
                    column_name = f"{category}_General"

                count = error_summary.get(category, {}).get(issue, 0)
                project_data_row[column_name] = count
                category_sum += count
            
            project_data_row[category] = category_sum
            total_project_errors += category_sum
            
        unknown_count = error_summary.get("Unknown", 0)
        project_data_row["Unknown"] = unknown_count
        total_project_errors += unknown_count
        project_data_row["Total Errors"] = total_project_errors

        data.append(project_data_row)

    # --- 4. Convert to DataFrame and add the total summary row ---
    if not data:
        print("No project data found to create a spreadsheet.")
        return
        
    df = pd.DataFrame(data)
    df.sort_values(by="Project Name", inplace=True)
    
    total_row = pd.Series(name="Total")
    total_row["Project Name"] = "Total"
    total_row["Status"] = ""

    # Sum all numeric columns for the total row using the unique internal names
    numeric_cols = ["CMD Count", "Elapsed Time"] + flat_specific_issue_columns + category_columns + ["Unknown", "Total Errors"]
    for col in numeric_cols:
        if col in df.columns:
            total_row[col] = df[col].sum()
    
    df = pd.concat([df, total_row.to_frame().T], ignore_index=False)

    # --- 5. Rename columns to the desired display names before exporting ---
    rename_map = {
        "Process Issue_General": "General",
        "Environment Issue_General": "General",
        "Project Issue_General": "General",
    }
    df.rename(columns=rename_map, inplace=True)

    # --- 6. Export to Excel ---
    df.to_excel("experiment_results.xlsx", index=False)
    print("Spreadsheet 'experiment_results.xlsx' created.")

# To run the function
if __name__ == "__main__":
    create_results_sheet()