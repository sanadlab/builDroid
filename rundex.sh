#!/bin/bash

for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
  if locale -a 2>/dev/null | grep -q "$LANG"; then
    export LANG
    break
  fi
done
export LC_COLLATE=C


python3 experimental_setups/increment_experiment.py
python3 construct_commands_descriptions.py
python3 prepare_ai_settings.py

#!/bin/bash

# Define the path to your text file
file_path="nightly_runs/runs_list.txt"

# Read the file line by line
while IFS= read -r line; do
    # Extract project name and GitHub URL from the line
    project_name=$(echo "$line" | awk '{print $1}')
    github_url=$(echo "$line" | awk '{print $2}')
    language=$(echo "$line" | awk '{print $3}')
    
    echo $project_name
    echo $github_url
    echo $language
    echo "{}" > ~/.docker/config.json
    # Call your Python script with project name and GitHub URL as parameters
    python clone_and_set_metadata.py "$project_name" "$github_url" "$language"
    ./run.sh --ai-settings ai_settings.yaml -c -l 40 -m json_file --experiment-file "project_meta_data.json"
    rm -rf auto_gpt_workspace/*
done < "$file_path"

