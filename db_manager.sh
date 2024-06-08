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
  (docker exec -i pnymanager-mysql-1 bash -c "mysqldump --no-tablespaces -hmysql -u ${DB_USERNAME} -p${DB_PASSWORD} pnymanager" | gzip >${DB_FILENAME}.sql.gz) & # Run the command in the background
  pid=$!                                                                                                                                                         # Get the process ID
  show_loading $pid                                                                                                                                              # Show the loading effect while the command is running

  # Wait until ${DB_FILENAME}.sql.gz is non-zero in size
  while [ ! -s ${DB_FILENAME}.sql.gz ]; do
    sleep 1
  done

  # Extract ${DB_FILENAME}.sql.gz to ${DB_FILENAME}.sql
  cp ${DB_FILENAME}.sql.gz ${DB_FILENAME}.sql.gz
  gzip -d ${DB_FILENAME}.sql.gz
  echo "Database exported and saved as ${DB_FILENAME}.sql"

  # Ask if the user wants to delete the ${DB_FILENAME}.sql.gz file
  read -p "Do you want to delete the ${DB_FILENAME}.sql.gz file? (yes/no): " delete_gz
  if [[ $delete_gz == "yes" ]]; then
    rm ${DB_FILENAME}.sql.gz
    echo "${DB_FILENAME}.sql.gz file deleted."
  else
    mv ${DB_FILENAME}.sql.gz ${DB_FILENAME}.sql.gz
    echo "${DB_FILENAME}.sql.gz file kept."
  fi
}

# Function to import the database
import_db() {
  if [ -f ${DB_FILENAME}.sql ]; then
    echo "Dropping existing database..."
    docker exec -i pnymanager-mysql-1 bash -c "mysql -u ${DB_USERNAME} -p${DB_PASSWORD} -P ${DB_PORT} -h ${DB_HOST} -e \"DROP DATABASE IF EXISTS ${DB_DATABASE}; CREATE DATABASE ${DB_DATABASE};\""
    wait $pid

    echo "Copying ${DB_FILENAME}.sql to the container..."
    docker cp ${DB_FILENAME}.sql pnymanager-mysql-1:/tmp/${DB_FILENAME}.sql
    sleep 2 # Wait for 5 seconds to ensure the file is ready

    echo "Verifying file size..."
    local_size=$(stat -c%s ${DB_FILENAME}.sql)
    remote_size=$(docker exec pnymanager-mysql-1 stat -c%s /tmp/${DB_FILENAME}.sql)

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
    echo "Error: ${DB_FILENAME}.sql file does not exist. Please make sure the ${DB_FILENAME}.sql file is present in the current directory."
  fi
}

# Function to import the database
run_import_database() {
  echo "Importing database..."
  docker exec -i pnymanager-mysql-1 bash -c "mysql -u ${DB_USERNAME} -p${DB_PASSWORD} -P ${DB_PORT} -h ${DB_HOST} pnymanager < /tmp/${DB_FILENAME}.sql" & # Run the command in the background
  pid=$!                                                                                                                     # Get the process ID
  show_loading $pid                                                                                                          # Show the loading effect while the command is running
  wait $pid
  echo "Database imported from ${DB_FILENAME}.sql"
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
