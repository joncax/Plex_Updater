@echo off
REM Change directory to where your main.py script is located
cd "C:\Scripts\Plex_Updater"

REM Activate your Python virtual environment if you are using one:
REM For example: "C:\path\to\your\venv\Scripts\activate.bat"
REM If you are not using a venv, you can comment out or remove the line below:
REM call "C:\path\to\your\venv\Scripts\activate.bat"

REM Run your main.py script
"C:\Program Files\Python311\python.exe" main.py

REM Keep the window open if debugging (remove or comment out for service)
REM pause