#!/bin/bash

# Function to display usage instructions
usage() {
  echo "Usage: $0 [option]"
  echo "Options:"
  echo "  -c, --containers-only   Stop and remove all Docker containers."
  echo "  -a, --all               Stop and remove all Docker containers, images, volumes, and networks."
  exit 1
}

# Default action
ACTION=""

# Parse arguments
if [[ $# -eq 0 ]]; then
  echo "Error: No option specified."
  usage
fi

while [[ "$#" -gt 0 ]]; do
  case $1 in
    -c|--containers-only)
      if [[ -n "$ACTION" ]]; then echo "Error: Specify only one action type."; usage; fi
      ACTION="containers"
      shift # past argument
      ;;
    -a|--all)
      if [[ -n "$ACTION" ]]; then echo "Error: Specify only one action type."; usage; fi
      ACTION="all"
      shift # past argument
      ;;
    *)
      echo "Error: Unknown option: $1"
      usage
      ;;
  esac
done

if [[ -z "$ACTION" ]]; then
    echo "Error: No valid action specified."
    usage
fi

# Determine warning message and operations based on action
WARNING_MESSAGE=""
DOCKER_COMMAND_DESC=""

if [[ "$ACTION" == "containers" ]]; then
  WARNING_MESSAGE="This will stop and remove ALL working Docker containers."
  DOCKER_COMMAND_DESC="Stopping and removing all containers..."
elif [[ "$ACTION" == "all" ]]; then
  WARNING_MESSAGE="This will stop and remove ALL working containers, images, volumes, and networks."
  DOCKER_COMMAND_DESC="Stopping all containers and pruning all Docker resources (containers, images, volumes, networks)..."
fi

# Confirmation prompt
while true; do
  read -p "WARNING! $WARNING_MESSAGE Continue? (yes/no): " user_input
  case "$user_input" in
    [Yy]* )
      break # Proceed with operations
      ;;
    [Nn]* )
      echo "Operation aborted by user."
      exit 0
      ;;
    * )
      echo "Please answer yes or no."
      ;;
  esac
done

echo "$DOCKER_COMMAND_DESC"

if [[ "$ACTION" == "containers" ]]; then
  # Stop all running containers (use xargs to handle no running containers gracefully)
  echo "Stopping running containers..."
  docker ps -q | xargs --no-run-if-empty docker kill

  # Remove all containers (stopped or otherwise)
  echo "Removing all containers..."
  docker container prune -f # Removes all stopped containers
  # If you want to be absolutely sure even about containers that might have failed to stop:
  # docker ps -aq | xargs --no-run-if-empty docker rm -f
  echo "Removed all containers."

elif [[ "$ACTION" == "all" ]]; then
  # Stop all running containers (kill is faster for this purpose)
  echo "Stopping running containers..."
  docker ps -q | xargs --no-run-if-empty docker kill

  # Prune everything: containers, images (used and unused), volumes, networks
  echo "Pruning system..."
  docker system prune -f -a --volumes
  echo "Removed all containers, images, volumes, and networks."
fi

echo "Operation complete."