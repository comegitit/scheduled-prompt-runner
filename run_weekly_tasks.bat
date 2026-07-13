REM run_weekly_tasks.bat - Chains multiple prompts for the weekly schedule.
REM
REM This is what Task Scheduler's weekly task actually calls, instead of
REM run_prompt.bat directly. Each line is a fully independent, stateless
REM run - if one fails, the next still executes (no dependency between
REM them). No changes to runner.py are needed to support this; it has no
REM awareness that chaining exists.

call C:\Projects\scheduled-prompt-runner\run_prompt.bat weekly inbox
call C:\Projects\scheduled-prompt-runner\run_prompt.bat weekly gmail