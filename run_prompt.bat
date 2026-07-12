REM run_prompt.bat - Task Scheduler launcher.
REM
REM Changes to the project directory and invokes the venv's Python
REM interpreter on runner.py directly (no activation step needed).
REM Output is appended to a separate log so failures in the launcher
REM itself (e.g. wrong path) are visible even if runner.py never starts.

cd /d C:\Projects\scheduled-prompt-runner
C:\Projects\scheduled-prompt-runner\venv\Scripts\python.exe runner.py >> run_prompt_bat.log 2>&1