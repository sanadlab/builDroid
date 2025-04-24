#!/bin/bash

# Default value for the number parameter
num=30

# Function to extract project name from GitHub URL
# Extracts the last component of the URL, which is usually the project name
extract_project_name() {
  local url="$1"
  echo "$url" | awk -F '/' '{print $(NF)}'
}

# Function to run the command and handle retries
run_with_retries() {
  local command="$1"
  local project_name="$2"
  local max_retries=1
  local attempt=1

  while [[ $attempt -le $max_retries ]]; do
    echo "======================================================================"
    echo "STARTING ITERATION $attempt:"
    echo "PROJECT: $project_name"
    echo "======================================================================"

    eval "$command"
    result=$(python3.10 post_process.py "$project_name")

    if [[ "$result" == "SUCCESS" ]]; then
      echo "Post-process succeeded. The extracted .apk file is in the experimental_setups/experiment_#/files/$project_name folder."
      return
    fi

    echo "Attempt $attempt failed with FAILURE. Retrying..."
    ((attempt++))
  done

  while false; do
    echo "======================================================================"
    echo "PROMPTING USER FOR ADDITIONAL RETRY:"
    echo "PROJECT: $project_name"
    echo "======================================================================"

    read -p "Post-process failed after $max_retries attempts. Do you want to retry again? (yes/no): " user_input
    case "$user_input" in
      [Yy]* ) eval "$command"; result=$(python3.10 post_process.py "$project_name");
              if [[ "$result" == "SUCCESS" ]]; then
                echo "Post-process succeeded."
                return
              fi
              ;;
      [Nn]* ) echo "Exiting retry loop."; break;;
      * ) echo "Please answer yes or no.";;
    esac
  done
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo_url="$2"
      shift 2
      ;;
    -l)
      num="$2"
      shift 2
      ;;
    *)
      if [[ -z "$repo_url" && -f "$1" ]]; then
        echo "Processing file: $1"
        repo_url="$1"
      fi
      shift
      ;;
  esac
done

# Set up API key, increment experiment, and prepare AI settings
python3.10 setup_api_key.py  # Sets up the API key required for the scripts
if [ $? -ne 0 ]; then
  exit 1
fi
python3.10 experimental_setups/increment_experiment.py  # Updates experimental parameters
python3.10 prepare_ai_settings.py  # Prepares the AI settings configuration

# Check for the --repo argument or file path
if [[ -n "$repo_url" ]]; then
  if [[ -f "$repo_url" ]]; then
    # Handle the case where the input is a file containing multiple repositories
    file_path="$repo_url"
    echo "Using file path: $file_path"  # Print the file path being processed
    mapfile -t repo_lines < "$file_path" # Read all lines into an array

    # Process each repository
    for line in "${repo_lines[@]}"; do
      # Parse each line to extract project name, GitHub URL
      github_url=$(echo "$line" | awk '{print $1}')
      project_name=$(extract_project_name "$github_url")

      echo "Project: $project_name"  # Print the project name
      echo "Github URL: $github_url"    # Print the GitHub URL

      # Initialize an empty Docker configuration file
      echo "{}" > ~/.docker/config.json

      # Call the Python script to clone the repo and set metadata
      python3.10 clone_and_set_metadata.py "$project_name" "$github_url"

      # Run the main script with specific AI settings and experiment parameters
      run_with_retries "./run.sh --ai-settings ai_settings.yaml -c -l \"$num\" -m json_file --experiment-file \"project_meta_data.json\"" "$project_name"
    done < "$file_path"
  
  else
    # Handle the case where the input is a single GitHub URL

    # Extract the project name from the provided GitHub URL
    project_name=$(extract_project_name "$repo_url")

    # Continue processing for a single repository
    echo "$project_name"  # Print the project name
    echo "$repo_url"      # Print the GitHub URL

    # Initialize an empty Docker configuration file
    echo "{}" > ~/.docker/config.json

    # Call the Python script to clone the repo and set metadata
    python3.10 clone_and_set_metadata.py "$project_name" "$repo_url"

    # Run the main script with specific AI settings and experiment parameters
    run_with_retries "./run.sh --ai-settings ai_settings.yaml -c -l \"$num\" -m json_file --experiment-file \"project_meta_data.json\"" "$project_name"
  fi
else
  # Handle invalid input cases
  echo "Error: Invalid input. Provide a file path or use --repo <github_repo_url>."
  echo "Usage: ./script_name.sh /path/to/file"
  echo "       ./script_name.sh --repo <github_repo_url>"
  exit 1
fi