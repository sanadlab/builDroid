#!/bin/bash

for LANG in en_AU.UTF-8 en_GB.UTF-8 C.UTF-8 C; do
  if locale -a 2>/dev/null | grep -q "$LANG"; then
    export LANG
    break
  fi
done
export LC_COLLATE=C

python3.10 setup_api_key.py
python3.10 experimental_setups/increment_experiment.py
python3.10 prepare_ai_settings.py

#!/bin/bash

# Define the path to your text file
if [ -z "$1" ]; then
  echo "Error: file_path argument not provided."
  echo "Usage: ./script_name.sh /path/to/file"
  exit 1
fi

# Assign the first argument to file_path
file_path="$1"

# Continue with the rest of the script
echo "Using file path: $file_path"


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
    python3.10 clone_and_set_metadata.py "$project_name" "$github_url" "$language"
    ./run.sh --ai-settings ai_settings.yaml -c -l 40 -m json_file --experiment-file "project_meta_data.json"
done < "$file_path"

