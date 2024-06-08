# docker-container-db-manager
A simple db micro tasks manager, like import, export and etc

## Start the Virtual Environment through venv

To Start a virtual environment run the following command\s

1. Create a virtual environment:
    
    `python3 -m venv venv`

2. Activate the virtual environment:

    `source venv/bin/activate`

## Installing required packages

- While venv is activated, run the following command to install required packages from the requirements.txt file:

    `pip install -r requirements.txt`

## Creating a distribution file

- To create a distribution file run the following command:
    
    `pyinstaller --onefile db_manager.py`

- You can specify the file name by adding the --name option. example adding a version number.

    `pyinstaller --onefile --name db_manager_x.x.x db_manager.py`