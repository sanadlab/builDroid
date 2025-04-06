while true; do
  read -p "WARNING! This will stop and remove all working containers and images. Continue? (y/n): " user_input
  case "$user_input" in
    [Yy]* )
      yes | docker kill $(docker ps -q);
      yes | docker system prune -a --volumes;
      echo "Removed all containers."; break;;
    [Nn]* ) echo "Exit."; break;;
    * ) echo "Please answer yes or no.";;
  esac
done