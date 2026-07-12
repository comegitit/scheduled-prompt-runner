REM run_prompt.bat - Task Scheduler launcher.
REM
REM Takes the task name (daily / weekly / monthly) as its one argument,
REM passed in by each scheduled task's action configuration. Changes to
REM the project directory and invokes the venv's Python interpreter on
REM runner.py directly (no activation step needed).
REM
REM Usage: run_prompt.bat daily

cd /d C:\Projects\scheduled-prompt-runner
C:\Projects\scheduled-prompt-runner\venv\Scripts\python.exe runner.py %1 >> run_prompt_bat.log 2>&1