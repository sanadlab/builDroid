#!/bin/bash

# Set container name
CONTAINER_NAME="epic_noyce"

# Find all APK paths in the container
apk_paths=$(docker exec "$CONTAINER_NAME" find / -name app-debug.apk 2>/dev/null)

# Loop through each path
while read -r apk_path; do
  # Extract project name from path
  # Assumes path format: /<project_name>/app/build/outputs/apk/debug/app-debug.apk
  project_name=$(echo "$apk_path" | cut -d'/' -f2)

  # Make directory on host
  mkdir -p "./$project_name"

  # Copy apk from container to host
  docker cp "$CONTAINER_NAME:$apk_path" "./apks/$project_name/app-debug.apk"

  echo "Extracted: $project_name/app-debug.apk"
done <<< "$apk_paths"
