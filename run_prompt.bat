REM run_prompt.bat - Task Scheduler launcher.
REM
REM Takes the task name (daily / weekly / monthly) and variant name as
REM its two arguments. Changes to the project directory and invokes the
REM venv's Python interpreter on runner.py directly (no activation step
REM needed).
REM
REM Usage: run_prompt.bat daily news
REM
REM For schedules with more than one variant chained together (e.g.
REM monthly), this .bat is called multiple times in sequence by a
REM wrapper .bat instead (see run_monthly_tasks.bat) rather than being
REM called directly by Task Scheduler.

cd /d C:\Projects\scheduled-prompt-runner
C:\Projects\scheduled-prompt-runner\venv\Scripts\python.exe runner.py %1 %2 >> run_prompt_bat.log 2>&1