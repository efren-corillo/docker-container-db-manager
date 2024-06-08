#!/usr/bin/env python3

import subprocess
import os
import time
import gzip
import shutil
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define constants for environment variables
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')
DB_HOST = os.getenv('DB_HOST')
DB_FILENAME = os.getenv('DB_FILENAME')
CONTAINER_NAMES = os.getenv('CONTAINER_NAMES')

def show_loading(pid):
    spinstr = '|/-\\'
    delay = 0.1
    while True:
        if subprocess.call(["ps", "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            break
        for char in spinstr:
            print(f' [{char}]', end='\r')
            time.sleep(delay)

def export_db(container_name):
    print(f"Exporting database from {container_name}...")
    process = subprocess.Popen(
        f"docker exec -i {container_name} bash -c 'mysqldump --no-tablespaces -hmysql -u {DB_USERNAME} -p{DB_PASSWORD} pnymanager' | gzip > {DB_FILENAME}.sql.gz",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    show_loading(process.pid)
    process.wait()

    while not os.path.exists(f'{DB_FILENAME}.sql.gz') or os.path.getsize(f'{DB_FILENAME}.sql.gz') == 0:
        time.sleep(1)

    shutil.copy(f'{DB_FILENAME}.sql.gz', f'temp_{DB_FILENAME}.sql.gz')
    with gzip.open(f'{DB_FILENAME}.sql.gz', 'rb') as f_in:
        with open(f'{DB_FILENAME}.sql', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"Database exported and saved as {DB_FILENAME}.sql")

    delete_gz = input(f"Do you want to delete the temp_{DB_FILENAME}.sql.gz file? (yes/no): ")
    if delete_gz.lower() == "yes":
        os.remove(f'temp_{DB_FILENAME}.sql.gz')
        print(f"temp_{DB_FILENAME}.sql.gz file deleted.")
    else:
        shutil.move(f'temp_{DB_FILENAME}.sql.gz', f'{DB_FILENAME}.sql.gz')
        print(f"{DB_FILENAME}.sql.gz file kept.")

def import_db(container_name):
    if os.path.isfile(f'{DB_FILENAME}.sql'):
        print(f"Dropping existing database in {container_name}...")
        process = subprocess.Popen(
            f"docker exec -i {container_name} bash -c 'mysql -u {DB_USERNAME} -p{DB_PASSWORD} -P {DB_PORT} -h {DB_HOST} -e \"DROP DATABASE IF EXISTS pnymanager; CREATE DATABASE pnymanager;\"'",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        show_loading(process.pid)
        process.wait()

        print(f"Copying {DB_FILENAME}.sql to the container...")
        subprocess.run(["docker", "cp", f"{DB_FILENAME}.sql", f"{container_name}:/tmp/{DB_FILENAME}.sql"])
        time.sleep(2)

        local_size = os.path.getsize(f'{DB_FILENAME}.sql')
        remote_size = int(subprocess.check_output(
            f"docker exec {container_name} stat -c%s /tmp/{DB_FILENAME}.sql", shell=True).strip())

        if local_size == remote_size:
            print("File successfully copied.")
            run_import_database(container_name)

            run_elastic = input(f"Do you want to run elastic:index on {container_name}? (yes/no): ")
            if run_elastic.lower() == "yes":
                run_elastic_index(container_name)
            else:
                print("Skipping elastic index.")

            update_passwords(container_name)
        else:
            print(f"Error: File size mismatch. Local size: {local_size} bytes, Remote size: {remote_size} bytes.")
    else:
        print(f"Error: {DB_FILENAME}.sql file does not exist. Please make sure the {DB_FILENAME}.sql file is present in the current directory.")

def run_import_database(container_name):
    print(f"Importing database to {container_name}...")
    process = subprocess.Popen(
        f"docker exec -i {container_name} bash -c 'mysql -u {DB_USERNAME} -p{DB_PASSWORD} -P {DB_PORT} -h {DB_HOST} pnymanager < /tmp/{DB_FILENAME}.sql'",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    show_loading(process.pid)
    process.wait()
    print(f"Database imported from {DB_FILENAME}.sql")

def update_passwords(container_name):
    change_passwords = input("Do you want to change every password in the Users table? (yes/no): ")
    if change_passwords.lower() == "yes":
        new_password = input("Enter the new password: ")
        print("Updating passwords...")
        process = subprocess.run(
            f"docker exec -i {container_name} bash -c \"echo \\\"User::query()->update(['password' => Hash::make('{new_password}')]);\\\" | php artisan tinker\"",
            shell=True
        )
        if process.returncode == 0:
            print(f"Passwords updated to '{new_password}' for all users.")
        else:
            print("Failed to update passwords.")
    else:
        print("Skipping password update.")

def run_elastic_index(container_name):
    print("Running 'php artisan elastic:index'...")
    process = subprocess.Popen(
        f"docker exec -i {container_name} bash -c 'php artisan elastic:index'",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    show_loading(process.pid)
    process.wait()
    print("'php artisan elastic:index' completed.")

def main():
    if CONTAINER_NAMES:
        container_list = CONTAINER_NAMES.strip('[]').replace(' ', '').split(',')
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
    print(f"1. export from {container_name}")
    print(f"2. import to {container_name}")
    print(f"3. run elastic:index in {container_name}")
    print("4. update password of all users")
    action = input("Enter the number of the task: ")

    if action == "1":
        export_db(container_name)
    elif action == "2":
        import_db(container_name)
    elif action == "3":
        run_elastic_index(container_name)
    elif action == "4":
        update_passwords(container_name)
    else:
        print("Invalid option. Please choose 1, 2, 3, or 4.")

if __name__ == "__main__":
    main()
