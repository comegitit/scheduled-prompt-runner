# Scheduled Prompt Runner

A minimal, single-purpose Python application that runs static prompts
against the Claude API on a schedule and emails the results. Built as a
deliberately lightweight companion to a larger agentic job-search
pipeline, showcasing the same orchestration principles - IMAP ingestion,
LLM scoring/generation, Task Scheduler automation - at a fraction of the
complexity.

## Status

- **Phase 1 (core loop):** Complete. Single prompt, manual test, scheduled
  test, all proven end to end.
- **Phase 2 (multiple prompts and schedules):** Complete. Three
  independently scheduled, functionally distinct tasks - daily, weekly,
  monthly - each with real data behind it (live web search, real inbox
  content).
- **Phase 3 (multiple prompts chained within a single scheduled task):**
  Complete. Every task now chains two prompts ("variants"), for six
  total prompts across three schedules. All six have been individually
  tested manually, and all three schedules have been proven end to end
  through their actual Task Scheduler trigger mechanism (not just
  manual `python runner.py` calls).

## What each task actually does

Each task now runs two variants in sequence. Both are independent,
stateless runs - if one fails or returns `NO_UPDATE`, the other still
executes.

| Task    | Variant       | Schedule              | Data source                                                                          | Behavior                                                                                          |
| ------- | ------------- | --------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Daily   | `news`        | Every day, 5:00 AM    | Web search, restricted to `anthropic.com`, `openai.com`                              | Notable Anthropic/OpenAI news from the last 24 hours.                                             |
| Daily   | `markets`     | Every day, 5:00 AM    | Web search, restricted to `nasdaqtrader.com`, `tsx.com`, `ir.thomsonreuters.com`     | Notable North American financial market news (S&P 500, NASDAQ, NYSE, TSX) from the last 24 hours. |
| Weekly  | `inbox`       | Sunday, 5:30 AM       | IMAP fetch of `roy@ai-yyc.com` since last Sunday                                     | Weekly email summary, grouped by sender, flagging anything needing action.                        |
| Weekly  | `gmail`       | Sunday, 5:30 AM       | IMAP fetch of `aggarwal.roy@gmail.com` since last Sunday                             | Same summary format, second mailbox.                                                              |
| Monthly | `deprecation` | 1st of month, 6:00 AM | Web search, restricted to `docs.claude.com`                                          | New Claude model deprecation/retirement announcements in the last 30 days.                        |
| Monthly | `governance`  | 1st of month, 6:00 AM | Web search, restricted to `canada.ca`, `alberta.ca`, `cigionline.org`, `betakit.com` | AI governance/regulatory developments, Canada and Alberta lens, last 30 days.                     |

Every prompt includes an explicit anti-hallucination instruction: verify
sources before answering, and prefer omission over a guess. Every prompt
supports a `NO_UPDATE` sentinel - if the response is exactly that string,
the run is logged and its output saved, but no email is sent.

## File Hierarchy

```
scheduled-prompt-runner/
├── runner.py                          # Entry point / orchestration
├── llm_client.py                      # Anthropic API wrapper (text + web search)
├── emailer.py                         # SMTP email wrapper
├── imap_client.py                     # IMAP inbox fetch wrapper (weekly variants only)
├── run_prompt.bat                     # Task Scheduler launcher (parameterized: task + variant)
├── run_daily_tasks.bat                # Chains daily's two variants
├── run_weekly_tasks.bat               # Chains weekly's two variants
├── run_monthly_tasks.bat              # Chains monthly's two variants
├── create_scheduled_task_daily.ps1    # Registers the daily task
├── create_scheduled_task_weekly.ps1   # Registers the weekly task
├── create_scheduled_task_monthly.ps1  # Registers the monthly task (see Known Issues)
├── requirements.txt
├── .env                                # Real secrets (gitignored)
├── .env.example                        # Blank template for version control
├── .gitignore
├── README.md
├── prompts/
│   ├── prompt_daily_news.txt
│   ├── prompt_daily_markets.txt
│   ├── prompt_weekly_inbox.txt
│   ├── prompt_weekly_gmail.txt
│   ├── prompt_monthly_deprecation.txt
│   └── prompt_monthly_governance.txt
└── output/
    └── output_<task>_<variant>_<date>.md   # Timestamped run results (gitignored)
```

The original single-prompt design (`prompt_current.txt`) has been fully
retired. Each (task, variant) pair now has its own dedicated prompt file.

## Module Specifications

### `runner.py`

Orchestration only. Usage: `python runner.py <task> <variant>`, e.g.
`python runner.py monthly governance`. Loads the matching prompt file,
injects live data where needed (IMAP for `inbox`/`gmail`, web search per
a per-variant domain allowlist for the others), calls the LLM, saves
output, and emails the result unless the response is exactly
`NO_UPDATE`. Has no knowledge that multiple variants exist per task -
chaining lives entirely at the `.bat`/Task Scheduler level. Logs every
step via a `TimedRotatingFileHandler` capped at 122 days of history.

### `llm_client.py`

Thin Anthropic API wrapper. `get_claude_response(prompt_text,
enable_web_search=False, allowed_domains=None)`. When web search is
enabled, results are restricted to an explicit domain allowlist per
variant - accuracy from a small number of trusted, first-party sources
rather than open web search. Model: `claude-sonnet-5`. Web search costs
$10 per 1,000 searches on top of standard token cost; negligible at this
run frequency.

### `emailer.py`

Thin SMTP wrapper. Sends via `mail.ai-yyc.com:587` with STARTTLS.

### `imap_client.py`

Thin IMAP wrapper. `fetch_weekly_emails(host, port, username, password)`
takes connection details as explicit arguments rather than reading
`.env` itself, so it works against any mailbox - `runner.py` decides
which account's credentials to supply per variant (see
`IMAP_ACCOUNT_CONFIG`). Fetches everything in the Inbox received since
last Sunday, no sender/subject filtering. Each email body is capped at
2,000 characters to bound prompt size.

### `run_prompt.bat`

Takes task and variant as two arguments (`run_prompt.bat monthly
governance`), invokes the venv's Python on `runner.py` directly. Called
either directly (not currently used that way by any registered task) or
by the three wrapper `.bat` files below.

### `run_daily_tasks.bat` / `run_weekly_tasks.bat` / `run_monthly_tasks.bat`

The actual Phase 3 mechanism. Each calls `run_prompt.bat` twice in
sequence, once per variant for that schedule. This is what each
scheduled task's Action actually points at - not `run_prompt.bat`
directly.

## Known Issues / Gotchas

- **PowerShell's `ScheduledTasks` module cannot reliably create OR
  trigger monthly tasks.** `New-ScheduledTaskTrigger` has no monthly
  parameter set at all (only Once, Daily, Weekly, AtLogOn, AtStartup).
  Working around this via CIM `MSFT_TaskMonthlyTrigger` objects hits a
  documented, unresolved PowerShell bug
  (github.com/PowerShell/PowerShell/issues/24651) that produces a
  misleading "user name or password is incorrect" error unrelated to
  actual credentials. `create_scheduled_task_monthly.ps1` works around
  registration by using `schtasks.exe` directly instead of
  `Register-ScheduledTask`.

  **This same underlying issue also breaks on-demand triggering.**
  `Start-ScheduledTask -TaskName "ScheduledPromptRunner_Monthly"`
  silently does nothing - no error, no new History entries, task just
  sits at "Ready" with no evidence it ran. The real scheduled trigger
  (1st of month, 6:00 AM) fires correctly since it goes through the OS
  scheduler service directly, bypassing the buggy PowerShell module -
  but for **on-demand testing of the monthly task, use `schtasks.exe`
  instead of `Start-ScheduledTask`:**

  ```
  schtasks /run /tn "ScheduledPromptRunner_Monthly"
  ```

  Tradeoff from the schtasks-only registration approach: the monthly
  task doesn't have the WakeToRun/restart-on-failure settings the daily
  and weekly tasks have, since schtasks.exe doesn't expose them.
  Acceptable here since the target machine never sleeps and is always on
  AC power - the only real loss is automatic retry if a single monthly
  run fails.

- **Task Scheduler's summary "Last Run Result" column can show `(0x1)`
  for a task that actually succeeded.** Observed on the weekly task
  after a wrapper `.bat` ran both variants successfully (confirmed via
  both the History tab, which said "successfully finished", and the
  actual `runner.log`/emails proving both variants completed). Likely
  an artifact of how `call` chains exit codes across two sequential
  commands in a `.bat` file. Don't trust the summary result code alone -
  check the History tab's actual event detail and the real logs.

- **Web search tool respects target sites' robots.txt / crawler
  policies.** Several mainstream news domains (Reuters, The Verge)
  reject Anthropic's crawler outright, which surfaces as a 400 error
  from the API, not a silent failure. Daily/monthly variants are
  restricted to small, curated domain lists partly for accuracy, partly
  to sidestep this. Domain lists sourced from outside research should
  still be verified empirically against the actual API - a domain being
  "not blocked by robots.txt" generically doesn't guarantee it's
  accessible to Anthropic's specific crawler user agent.

- **VS Code's integrated terminal must have the venv interpreter
  selected** (`Python: Select Interpreter` → the `.\venv\Scripts\python.exe`
  entry) for new terminals to auto-activate. Existing open terminals
  don't retroactively activate - open a fresh one after selecting.

- **Elevated PowerShell opens in `C:\Windows\system32` by default**, not
  wherever your other terminal was. Always `cd` into the project
  directory first when running any of the `create_scheduled_task_*.ps1`
  scripts, or `schtasks`, from an Administrator prompt.

## Dependencies

| Dependency                | Purpose                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| Python 3.11+              | Runtime                                                                                           |
| `anthropic`               | Claude API access, including the web search tool                                                  |
| `python-dotenv`           | Loads `.env` into environment variables                                                           |
| Windows Task Scheduler    | OS-level scheduling                                                                               |
| SMTP mailbox              | `mail.ai-yyc.com:587` (STARTTLS) - outbound email for all tasks                                   |
| IMAP mailbox (ai-yyc.com) | `mail.ai-yyc.com:993` (SSL) - weekly `inbox` variant                                              |
| IMAP mailbox (Gmail)      | `imap.gmail.com:993` (SSL), requires a Gmail App Password (2FA required) - weekly `gmail` variant |

## Setup

1. `python -m venv venv` (from a **non-elevated** terminal), then
   `.\venv\Scripts\Activate.ps1`.
2. `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in real values: Anthropic API
   key, SMTP credentials, both sets of IMAP credentials. Gmail requires
   generating an App Password under Google Account → Security → 2-Step
   Verification → App Passwords.
4. Test each of the six variants manually before scheduling anything:
   ```
   python runner.py daily news
   python runner.py daily markets
   python runner.py weekly inbox
   python runner.py weekly gmail
   python runner.py monthly deprecation
   python runner.py monthly governance
   ```
5. From an **elevated** PowerShell (remember to `cd` into the project
   directory first), run each scheduler script once:
   ```
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_daily.ps1
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_weekly.ps1
   powershell -ExecutionPolicy Bypass -File .\create_scheduled_task_monthly.ps1
   ```
6. Verify all three in Task Scheduler (`taskschd.msc`) - confirm each
   task's Actions tab points at its wrapper `.bat`
   (`run_daily_tasks.bat` etc.), not `run_prompt.bat` directly.
7. Test each on-demand before trusting the real schedule:
   ```
   Start-ScheduledTask -TaskName "ScheduledPromptRunner_Daily"
   Start-ScheduledTask -TaskName "ScheduledPromptRunner_Weekly"
   schtasks /run /tn "ScheduledPromptRunner_Monthly"
   ```
   (Note the monthly task uses `schtasks /run`, not `Start-ScheduledTask`
   - see Known Issues.) Confirm two new log entries appear per task, one
     per variant, in both `run_prompt_bat.log` and `runner.log`.

## Security Notes

- `.env` holds real secrets and is gitignored. Verify `.gitignore` exists
  and lists `.env` _before_ the first `git add` in any fresh clone.

## This repository is public, and intended to demonstrate my agentic python coding skills.
