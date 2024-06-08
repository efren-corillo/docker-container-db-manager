#!/bin/bash

# Function to show loading effect
show_loading() {
  local pid=$1
  local delay=0.1
  local spinstr='|/-\'
  while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
    local temp=${spinstr#?}
    printf " [%c]  " "$spinstr"
    local spinstr=$temp${spinstr%"$temp"}
    sleep $delay
    printf "\b\b\b\b\b\b"
  done
  printf "    \b\b\b\b"
}

# Function to export the database
export_db() {
  echo "Exporting database..."
  (docker exec -i pnymanager-mysql-1 bash -c 'mysqldump --no-tablespaces -hmysql -u pnymanager -pqwerty pnymanager' | gzip >dump.sql.gz) & # Run the command in the background
  pid=$!                                                                                                                                   # Get the process ID
  show_loading $pid                                                                                                                        # Show the loading effect while the command is running

  # Wait until dump.sql.gz is non-zero in size
  while [ ! -s dump.sql.gz ]; do
    sleep 1
  done

  # Extract dump.sql.gz to dump.sql
  cp dump.sql.gz temp_dump.sql.gz
  gzip -d dump.sql.gz
  echo "Database exported and saved as dump.sql"

  # Ask if the user wants to delete the temp_dump.sql.gz file
  read -p "Do you want to delete the temp_dump.sql.gz file? (yes/no): " delete_gz
  if [[ $delete_gz == "yes" ]]; then
    rm temp_dump.sql.gz
    echo "temp_dump.sql.gz file deleted."
  else
    mv temp_dump.sql.gz dump.sql.gz
    echo "dump.sql.gz file kept."
  fi
}

# Function to import the database
import_db() {
  if [ -f dump.sql ]; then
    echo "Dropping existing database..."
    docker exec -i pnymanager-mysql-1 bash -c 'mysql -u pnymanager -pqwerty -P 3306 -h 127.0.0.1 -e "DROP DATABASE IF EXISTS pnymanager; CREATE DATABASE pnymanager;"'
    wait $pid

    echo "Copying dump.sql to the container..."
    docker cp dump.sql pnymanager-mysql-1:/tmp/dump.sql
    sleep 2 # Wait for 5 seconds to ensure the file is ready

    echo "Verifying file size..."
    local_size=$(stat -c%s dump.sql)
    remote_size=$(docker exec pnymanager-mysql-1 stat -c%s /tmp/dump.sql)

    if [ "$local_size" -eq "$remote_size" ]; then
      echo "File successfully copied."

      run_import_database

      read -p "Do you want to run elastic:index on pnymanager-website-1? (yes/no): " run_elastic
      if [[ $run_elastic == "yes" ]]; then
        run_elastic_index
      else
        echo "Skipping elastic index."
      fi

      update_passwords
    else
      echo "Error: File size mismatch. Local size: $local_size bytes, Remote size: $remote_size bytes."
    fi
  else
    echo "Error: dump.sql file does not exist. Please make sure the dump.sql file is present in the current directory."
  fi
}

# Function to import the database
run_import_database() {
  echo "Importing database..."
  docker exec -i pnymanager-mysql-1 bash -c 'mysql -u pnymanager -pqwerty -P 3306 -h 127.0.0.1 pnymanager < /tmp/dump.sql' & # Run the command in the background
  pid=$!                                                                                                                     # Get the process ID
  show_loading $pid                                                                                                          # Show the loading effect while the command is running
  wait $pid
  echo "Database imported from dump.sql"
}

# Function to update user passwords
update_passwords() {
  read -p "Do you want to change every password in the Users table? (yes/no): " change_passwords
  if [[ $change_passwords == "yes" ]]; then
    read -s -p "Enter the new password: " new_password
    echo
    echo "Updating passwords..."
    docker exec -i pnymanager-website-1 bash -c "echo \"User::query()->update(['password' => Hash::make('$new_password')]);\" | php artisan tinker"
    if [ $? -eq 0 ]; then
      echo "Passwords updated to '$new_password' for all users."
    else
      echo "Failed to update passwords."
    fi
  else
    echo "Skipping password update."
  fi
}

# Function to run php artisan elastic:index
run_elastic_index() {
  echo "Running 'php artisan elastic:index'..."
  docker exec -i pnymanager-website-1 bash -c 'php artisan elastic:index' & # Run the command in the background
  pid=$!                                                                    # Get the process ID
  # show_loading $pid # Show the loading effect while the command is running
  wait $pid
  echo "'php artisan elastic:index' completed."
}

# Main script
echo "What would you like to do?"
echo "1. export from pnymanager-mysql-1"
echo "2. import to pnymanager-mysql-1"
echo "3. run elastic:index in pnymanager-website-1"
echo "4. update password of all users"
read -p "Enter the number of the task: " action

case $action in
1)
  export_db
  ;;
2)
  import_db
  ;;
3)
  run_elastic_index
  ;;
4)
  update_passwords
  ;;
*)
  echo "Invalid option. Please choose 1,2,3 or 4."
  ;;
esac
