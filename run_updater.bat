@echo off
REM --- Set the directory where your main.py script located ---
SET SCRIPT_DIR=C:\Scripts\Plex_Updater

REM --- Change to the script's directory ---
CD /D %SCRIPT_DIR%

REM --- Activate a virtual environment if you used one (optional, uncomment if needed) ---
REM CALL %SCRIPT_DIR%\venv\Scripts\activate.bat

REM --- Run the Python script ---
REM Using 'python' assumes Python is in your system's PATH.
REM If you installed Python for a specific user or in a non-standard way,
REM you might need to specify the full path to your python.exe.
REM Example: "C:\Users\YourUser\AppData\Local\Programs\Python\Python39\python.exe" main.py
python main.py

REM --- Exit with the Python script's exit code ---
EXIT /B %ERRORLEVEL%