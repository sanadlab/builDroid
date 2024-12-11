#!/bin/bash

# Function to extract project name from GitHub URL
# Extracts the last component of the URL, which is usually the project name
extract_project_name() {
  local url="$1"
  echo "$url" | awk -F '/' '{print $(NF)}'
}

# Set up API key, increment experiment, and prepare AI settings
python3.10 setup_api_key.py  # Sets up the API key required for the scripts
python3.10 experimental_setups/increment_experiment.py  # Updates experimental parameters
python3.10 prepare_ai_settings.py  # Prepares the AI settings configuration

# Check for the --repo argument or file path
if [[ "$1" == "--repo" ]]; then
  # Ensure the user provided a GitHub URL with the --repo argument
  if [[ -z "$2" ]]; then
    echo "Error: --repo argument requires a GitHub URL."
    echo "Usage: ./script_name.sh --repo <github_repo_url>"
    exit 1
  fi

  # Extract the project name from the provided GitHub URL
  github_url="$2"
  project_name=$(extract_project_name "$github_url")

  # Call get_main_language.py to determine the main language of the repository
  # The Python script is expected to return a string like "Primary language: <language>"
  primary_language=$(python3.10 get_main_language.py "$github_url")
  echo "$primary_language"

  # Continue processing for a single repository
  echo "$project_name"  # Print the project name
  echo "$github_url"    # Print the GitHub URL

  # Initialize an empty Docker configuration file
  echo "{}" > ~/.docker/config.json

  # Call the Python script to clone the repo and set metadata
  python3.10 clone_and_set_metadata.py "$project_name" "$github_url" "$primary_language"

  # Run the main script with specific AI settings and experiment parameters
  ./run.sh --ai-settings ai_settings.yaml -c -l 40 -m json_file --experiment-file "project_meta_data.json"

elif [[ -f "$1" ]]; then
  # Handle the case where the input is a file containing multiple repositories
  file_path="$1"
  echo "Using file path: $file_path"  # Print the file path being processed

  # Read the file line by line
  while IFS= read -r line; do
      # Parse each line to extract project name, GitHub URL, and language
      project_name=$(echo "$line" | awk '{print $1}')
      github_url=$(echo "$line" | awk '{print $2}')
      language=$(echo "$line" | awk '{print $3}')

      echo "$project_name"  # Print the project name
      echo "$github_url"    # Print the GitHub URL
      echo "$language"      # Print the specified language

      # Initialize an empty Docker configuration file
      echo "{}" > ~/.docker/config.json

      # Call the Python script to clone the repo and set metadata
      python3.10 clone_and_set_metadata.py "$project_name" "$github_url" "$language"

      # Run the main script with specific AI settings and experiment parameters
      ./run.sh --ai-settings ai_settings.yaml -c -l 40 -m json_file --experiment-file "project_meta_data.json"
  done < "$file_path"

else
  # Handle invalid input cases
  echo "Error: Invalid input. Provide a file path or use --repo <github_repo_url>."
  echo "Usage: ./script_name.sh /path/to/file"
  echo "       ./script_name.sh --repo <github_repo_url>"
  exit 1
fi