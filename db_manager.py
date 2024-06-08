#!/usr/bin/env python3

import subprocess
import os
import time
import gzip
import shutil
from dotenv import load_dotenv

def show_loading(pid):
    spinstr = '|/-\\'
    delay = 0.1
    while True:
        if subprocess.call(["ps", "-p", str(pid)]) != 0:
            break
        for char in spinstr:
            print(f' [{char}]', end='\r')
            time.sleep(delay)

def export_db():
    print("Exporting database...")
    process = subprocess.Popen(
        "docker exec -i pnymanager-mysql-1 bash -c 'mysqldump --no-tablespaces -hmysql -u ${DB_USERNAME} -p${DB_PASSWORD} pnymanager' | gzip > ${DB_FILENAME}.sql.gz",
        shell=True
    )
    show_loading(process.pid)
    process.wait()

    while not os.path.exists('${DB_FILENAME}.sql.gz') or os.path.getsize('${DB_FILENAME}.sql.gz') == 0:
        time.sleep(1)

    shutil.copy('${DB_FILENAME}.sql.gz', 'temp_${DB_FILENAME}.sql.gz')
    with gzip.open('${DB_FILENAME}.sql.gz', 'rb') as f_in:
        with open('${DB_FILENAME}.sql', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print("Database exported and saved as ${DB_FILENAME}.sql")

    delete_gz = input("Do you want to delete the temp_${DB_FILENAME}.sql.gz file? (yes/no): ")
    if delete_gz.lower() == "yes":
        os.remove('temp_${DB_FILENAME}.sql.gz')
        print("temp_${DB_FILENAME}.sql.gz file deleted.")
    else:
        shutil.move('temp_${DB_FILENAME}.sql.gz', '${DB_FILENAME}.sql.gz')
        print("${DB_FILENAME}.sql.gz file kept.")

def import_db():
    if os.path.isfile('${DB_FILENAME}.sql'):
        print("Dropping existing database...")
        process = subprocess.Popen(
            "docker exec -i pnymanager-mysql-1 bash -c 'mysql -u ${DB_USERNAME} -p${DB_PASSWORD} -P ${DB_PORT} -h ${DB_HOST} -e \"DROP DATABASE IF EXISTS pnymanager; CREATE DATABASE pnymanager;\"'",
            shell=True
        )
        show_loading(process.pid)
        process.wait()

        print("Copying ${DB_FILENAME}.sql to the container...")
        subprocess.run(["docker", "cp", "${DB_FILENAME}.sql", "pnymanager-mysql-1:/tmp/${DB_FILENAME}.sql"])
        time.sleep(2)

        local_size = os.path.getsize('${DB_FILENAME}.sql')
        remote_size = int(subprocess.check_output(
            "docker exec pnymanager-mysql-1 stat -c%s /tmp/${DB_FILENAME}.sql", shell=True).strip())

        if local_size == remote_size:
            print("File successfully copied.")
            run_import_database()

            run_elastic = input("Do you want to run elastic:index on pnymanager-website-1? (yes/no): ")
            if run_elastic.lower() == "yes":
                run_elastic_index()
            else:
                print("Skipping elastic index.")

            update_passwords()
        else:
            print(f"Error: File size mismatch. Local size: {local_size} bytes, Remote size: {remote_size} bytes.")
    else:
        print("Error: ${DB_FILENAME}.sql file does not exist. Please make sure the ${DB_FILENAME}.sql file is present in the current directory.")

def run_import_database():
    print("Importing database...")
    process = subprocess.Popen(
        "docker exec -i pnymanager-mysql-1 bash -c 'mysql -u ${DB_USERNAME} -p${DB_PASSWORD} -P ${DB_PORT} -h ${DB_HOST} pnymanager < /tmp/${DB_FILENAME}.sql'",
        shell=True
    )
    show_loading(process.pid)
    process.wait()
    print("Database imported from ${DB_FILENAME}.sql")

def update_passwords():
    change_passwords = input("Do you want to change every password in the Users table? (yes/no): ")
    if change_passwords.lower() == "yes":
        new_password = input("Enter the new password: ")
        print("Updating passwords...")
        process = subprocess.run(
            f"docker exec -i pnymanager-website-1 bash -c \"echo \\\"User::query()->update(['password' => Hash::make('{new_password}')]);\\\" | php artisan tinker\"",
            shell=True
        )
        if process.returncode == 0:
            print(f"Passwords updated to '{new_password}' for all users.")
        else:
            print("Failed to update passwords.")
    else:
        print("Skipping password update.")

def run_elastic_index():
    print("Running 'php artisan elastic:index'...")
    process = subprocess.Popen(
        "docker exec -i pnymanager-website-1 bash -c 'php artisan elastic:index'",
        shell=True
    )
    show_loading(process.pid)
    process.wait()
    print("'php artisan elastic:index' completed.")

def main():
    container_names = os.getenv('CONTAINER_NAMES')
    if container_names:
        container_list = container_names.strip('[]').split(', ')
    else:
        print("CONTAINER_NAMES environment variable is not set.")
        return

    print("Which container would you like to interact with?")
    for idx, container in enumerate(container_list, start=1):
        print(f"{idx}. {container}")
    container_choice = int(input("Enter the number here: ")) - 1

    if 0 <= container_choice < len(container_list):
        container_name = container_list[container_choice]
    else:
        print("Invalid choice. Exiting.")
        return

    print("What would you like to do?")
    print("1. export from "+ container_name)
    print("2. import to "+ container_name)
    print("3. run elastic:index in "+ container_name)
    print("4. update password of all users")
    action = input("Enter the number of the task: ")

    if action == "1":
        export_db(container_name)
    elif action == "2":
        import_db(container_name)
    elif action == "3":
        run_elastic_index()
    elif action == "4":
        update_passwords()
    else:
        print("Invalid option. Please choose 1, 2, 3, or 4.")

if __name__ == "__main__":
    main()
