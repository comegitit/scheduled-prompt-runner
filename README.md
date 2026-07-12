# Scheduled Prompt Runner

A minimal, single-purpose Python application that runs a static prompt
against the Claude API on a schedule and emails the result. Built as a
deliberately lightweight companion to a larger agentic job-search
pipeline, showcasing the same orchestration principles - IMAP ingestion,
LLM scoring/generation, Task Scheduler automation - at a fraction of the
complexity.

## Status

- **Phase 1 (core loop):** Complete. Single prompt, manual test, scheduled
  test, all proven end to end.
- **Phase 2 (multiple prompts and schedules):** Complete, and exceeded
  original scope. Three independently scheduled, functionally distinct
  tasks - daily, weekly, monthly - each with real data behind it (live
  web search, real inbox content), not just placeholder prompts.
- **Phase 3 (multiple prompts chained within a single scheduled task):**
  Not yet started. Planned next.

## What each task actually does

| Task    | Schedule              | Data source                                                | Behavior                                                                                                                                      |
| ------- | --------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Daily   | Every day, 5:00 AM    | Web search, restricted to `anthropic.com` and `openai.com` | Reports notable Anthropic/OpenAI news from the last 24 hours. Returns `NO_UPDATE` (no email sent) if nothing new.                             |
| Weekly  | Sunday, 5:30 AM       | IMAP fetch of the `roy@ai-yyc.com` Inbox since last Sunday | Summarizes the week's emails, grouped by sender, flagging anything needing action. Returns `NO_UPDATE` if the inbox was empty for the window. |
| Monthly | 1st of month, 6:00 AM | Web search, restricted to `docs.claude.com`                | Checks for new Claude model deprecation/retirement announcements in the last 30 days. Returns `NO_UPDATE` if none.                            |

All three prompts include an explicit anti-hallucination instruction:
verify sources before answering, and prefer omission over a guess.

## File Hierarchy

```
scheduled-prompt-runner/
├── runner.py                          # Entry point / orchestration
├── llm_client.py                      # Anthropic API wrapper (text + web search)
├── emailer.py                         # SMTP email wrapper
├── imap_client.py                     # IMAP inbox fetch wrapper (weekly task only)
├── run_prompt.bat                     # Task Scheduler launcher (parameterized by task name)
├── create_scheduled_task_daily.ps1    # Registers the daily task
├── create_scheduled_task_weekly.ps1   # Registers the weekly task
├── create_scheduled_task_monthly.ps1  # Registers the monthly task (see note below)
├── requirements.txt
├── .env                                # Real secrets (gitignored)
├── .env.example                        # Blank template for version control
├── .gitignore
├── README.md
├── prompts/
│   ├── prompt_daily.txt
│   ├── prompt_weekly.txt
│   └── prompt_monthly.txt
└── output/
    └── output_<task>_<date>.md         # Timestamped run results (gitignored)
```

`prompt_current.txt` from the original single-prompt design has been
retired - each task now has its own dedicated prompt file, selected by a
required command-line argument to `runner.py`.

## Module Specifications

### `runner.py`

Orchestration only. Usage: `python runner.py <daily|weekly|monthly>`.
Loads the matching prompt file, injects live data where needed (see
`build_prompt()`), calls the LLM, saves output, and emails the result
unless the response is exactly `NO_UPDATE`. Logs every step via a
`TimedRotatingFileHandler` capped at 122 days of history.

### `llm_client.py`

Thin Anthropic API wrapper. `get_claude_response(prompt_text,
enable_web_search=False, allowed_domains=None)`. When web search is
enabled, results are restricted to an explicit domain allowlist -
accuracy from a small number of trusted, first-party sources rather than
open web search. Model: `claude-sonnet-5`. Web search costs $10 per 1,000
searches on top of standard token cost; negligible at this run frequency.

### `emailer.py`

Thin SMTP wrapper. Sends via `mail.ai-yyc.com:587` with STARTTLS.

### `imap_client.py`

Thin IMAP wrapper, used only by the weekly task.
`fetch_weekly_emails()` connects to the Inbox, fetches everything
received since last Sunday (no sender/subject filtering), and returns a
formatted text blob for injection into the weekly prompt. Each email body
is capped at 2,000 characters to bound prompt size.

## Known Issues / Gotchas

- **PowerShell's `ScheduledTasks` module cannot reliably create monthly
  triggers.** `New-ScheduledTaskTrigger` has no monthly parameter set at
  all, and working around it via CIM `MSFT_TaskMonthlyTrigger` objects
  hits a documented, unresolved PowerShell bug
  (github.com/PowerShell/PowerShell/issues/24651) that produces a
  misleading "user name or password is incorrect" error unrelated to
  actual credentials. `create_scheduled_task_monthly.ps1` works around
  this by using `schtasks.exe` directly instead of the PowerShell
  cmdlets. Tradeoff: the monthly task doesn't have the
  WakeToRun/restart-on-failure settings the daily and weekly tasks have,
  since schtasks.exe doesn't expose them. Acceptable here since the
  target machine never sleeps and is always on AC power - the only real
  loss is automatic retry if a single monthly run fails.
- **Web search tool respects target sites' robots.txt / crawler
  policies.** Several mainstream news domains (Reuters, The Verge)
  reject Anthropic's crawler outright, which surfaces as a 400 error
  from the API, not a silent failure. The daily task is restricted to
  first-party company domains (`anthropic.com`, `openai.com`) partly for
  accuracy, partly to sidestep this entirely.
- **VS Code's integrated terminal must have the venv interpreter
  selected** (`Python: Select Interpreter` → the `.\venv\Scripts\python.exe`
  entry) for new terminals to auto-activate. Existing open terminals
  don't retroactively activate - open a fresh one after selecting.
- **Elevated PowerShell opens in `C:\Windows\system32` by default**, not
  wherever your other terminal was. Always `cd` into the project
  directory first when running any of the `create_scheduled_task_*.ps1`
  scripts from an Administrator prompt.

## Dependencies

| Dependency             | Purpose                                                             |
| ---------------------- | ------------------------------------------------------------------- |
| Python 3.11+           | Runtime                                                             |
| `anthropic`            | Claude API access, including the web search tool                    |
| `python-dotenv`        | Loads `.env` into environment variables                             |
| Windows Task Scheduler | OS-level scheduling                                                 |
| SMTP mailbox           | `mail.ai-yyc.com:587` (STARTTLS) - outbound email for all tasks     |
| IMAP mailbox           | `mail.ai-yyc.com:993` (SSL) - inbound read access, weekly task only |

## Setup

1. `python -m venv venv` (from a **non-elevated** terminal), then
   `.\venv\Scripts\Activate.ps1`.
2. `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in real values: Anthropic API
   key, SMTP credentials, IMAP credentials.
4. Test each task manually before scheduling anything:
   ```
   python runner.py daily
   python runner.py weekly
   python runner.py monthly
   ```
5. From an **elevated** PowerShell (remember to `cd` into the project
   directory first), run each scheduler script once:
   ```
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_daily.ps1
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_weekly.ps1
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_monthly.ps1
   ```
6. Verify all three in Task Scheduler (`taskschd.msc`), and test each
   on-demand with `Start-ScheduledTask -TaskName "<name>"` before
   trusting the real schedule.

## Planned: Phase 3

Chain multiple prompts within a single scheduled task (e.g. a monthly
task running both the deprecation check and a second, unrelated prompt).
No changes to `runner.py` expected - each invocation stays a fully
independent, stateless run. Likely implementation: `run_prompt.bat`
calling `runner.py` multiple times in sequence, one call per prompt.

## Security Notes

- `.env` holds real secrets and is gitignored. Verify `.gitignore` exists
  and lists `.env` _before_ the first `git add` in any fresh clone.
- If this repository is ever made public, check `git log --all
--full-history -- .env` first to confirm it was never committed -
  removing a file in a later commit does not remove it from history.
