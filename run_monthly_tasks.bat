REM run_monthly_tasks.bat - Chains multiple prompts for the monthly schedule.
REM
REM This is what Task Scheduler's monthly task actually calls, instead of
REM run_prompt.bat directly. Each line is a fully independent, stateless
REM run - if one fails, the next still executes (no dependency between
REM them). No changes to runner.py are needed to support this; it has no
REM awareness that chaining exists.

call C:\Projects\scheduled-prompt-runner\run_prompt.bat monthly deprecation
call C:\Projects\scheduled-prompt-runner\run_prompt.bat monthly governance