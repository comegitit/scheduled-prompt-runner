# Scheduled Prompt Runner - Project Blueprint

## This app is a simple agentic Python project. It is meant to demonstrate my ability to create agentic AI apps, using the Anthropic Claude Sonnet API

#

## 1. Problem Statement

Recurring, well-defined analytical or research tasks (e.g. "summarize this
week's AI governance news," "check if a vendor's API model is being
deprecated") currently require manually opening a chat interface, writing
or re-pasting a prompt, and reading the result - every single time. There
is no lightweight way to have a static, well-tuned prompt run on a
schedule and deliver its output passively, without building or paying for
a full automation platform.

## 2. Solution Overview

A minimal, single-purpose Python application that:

1. Loads a static prompt from a text file.
2. Sends that prompt to the Claude API.
3. Saves the response as a timestamped markdown file.
4. Emails the response to the user.
5. Is triggered on a schedule by the operating system (Windows Task
   Scheduler), not by any logic inside the app itself.

The application is deliberately **not** an agent framework. It has no
planning loop, no tool use, no memory between runs, and no dynamic prompt
construction. Each run is a single, stateless, one-shot LLM call. All
"intelligence" about _what_ to ask lives in the prompt text file, which is
treated as data, not code. This keeps the codebase small, auditable, and
easy to extend without introducing unnecessary abstraction.

### Design Principles

- **Prompt is data, not code.** Editing behavior means editing a `.txt`
  file, never touching Python.
- **One module, one responsibility.** The LLM call, the email send, and
  the run orchestration are three separate files that don't know about
  each other's internals.
- **The OS owns scheduling.** The app has no concept of "when" - it just
  runs once, correctly, when invoked. Task Scheduler decides when that
  happens.
- **Fail loudly, not silently.** A broken run should notify the user by
  email, not just vanish into a log file nobody checks.
- **No premature abstraction.** Multi-prompt and multi-schedule support
  (see Section 8) are deferred until the single-prompt case is proven, not
  designed in from day one.

## 3. Out of Scope (Explicit Non-Goals)

- No IMAP/email-reading capability. This app only sends email; it does
  not read any inbox. (A separate concern from the author's existing
  agentic job-search pipeline, which does read email via IMAP.)
- No web-browsing or tool-use capability in the initial build. If a
  prompt references a live URL, it will be answered from the model's
  training data unless the web-search tool is explicitly added later
  (see Section 8).
- No database, no persistent state between runs, no conversation history.
- No user interface. Configuration is done by editing `.env` and prompt
  `.txt` files directly.
- No multi-user support. Single operator, single mailbox.

## 4. File Hierarchy

```
scheduled-prompt-runner/
├── runner.py                  # Entry point / orchestration
├── llm_client.py               # Anthropic API wrapper
├── emailer.py                  # SMTP email wrapper
├── run_prompt.bat              # Task Scheduler launcher
├── create_scheduled_task.ps1   # One-time setup script for Task Scheduler
├── requirements.txt            # Python dependencies
├── .env                        # Real secrets (gitignored, never committed)
├── .env.example                # Blank template for version control
├── .gitignore
├── README.md                   # This document, or a condensed version of it
├── prompts/
│   └── prompt_current.txt      # The active prompt (data, not code)
└── output/
    └── output_YYYY-MM-DD.md    # Timestamped run results (gitignored)
```

## 5. Module Specifications

### 5.1 `runner.py` (orchestration)

**Responsibility:** Coordinate the run. Contains no prompt logic, no API
details, no email details.

**Behavior:**

1. Load environment variables from `.env`.
2. Read the prompt text from `prompts/prompt_current.txt`. Fail clearly if
   missing or empty.
3. Pass the prompt text to `llm_client` and receive the response text.
4. Save the response to `output/output_<date>.md`.
5. Check the response for a `NO_UPDATE` sentinel (see Section 7). If
   present, log and exit without emailing.
6. Otherwise, pass the response to `emailer` to send.
7. Log every step (start, prompt loaded, response received, output saved,
   email sent) to both console and a log file, so unattended runs are
   auditable after the fact.
8. On any exception: log the full error, attempt to send a
   failure-notification email, and exit with a non-zero status code (so
   Task Scheduler can be configured to detect failed runs).

### 5.2 `llm_client.py` (Claude API wrapper)

**Responsibility:** Send one prompt, get one text response back. No
orchestration, no email logic.

**Behavior:**

- Read the API key from the environment.
- Call the Anthropic Messages API with the given prompt as a single user
  message.
- Use the current generally-available Sonnet model (confirm the exact
  model string against Anthropic's docs at build time, as this changes
  over time).
- Extract and return only the text content of the response.
- Translate connection errors, API error statuses, and empty responses
  into clear, distinct exceptions the caller can log meaningfully.

### 5.3 `emailer.py` (SMTP wrapper)

**Responsibility:** Send one email. No prompt logic, no orchestration.

**Behavior:**

- Read SMTP host, port, username, password, and recipient from the
  environment. Fail clearly if any required setting is missing.
- Compose a plain-text (or markdown-as-text) email with the given subject
  and body.
- Optionally attach the saved output file.
- Send via `smtplib` with STARTTLS.

### 5.4 `run_prompt.bat` (Task Scheduler launcher)

A minimal batch script that changes to the project directory and invokes
the Python interpreter on `runner.py`, redirecting output to a log file.
This is the only thing Task Scheduler needs to know how to run.

### 5.5 `create_scheduled_task.ps1` (setup script)

A one-time PowerShell script (run manually, as Administrator) that
registers the Windows Scheduled Task: sets the trigger (day/time),
points the action at `run_prompt.bat`, and configures settings such as
retry behavior and execution time limit. Not part of the running
application - a setup utility only.

## 6. Dependencies

| Dependency                        | Purpose                                         |
| --------------------------------- | ----------------------------------------------- |
| Python 3.11+                      | Runtime                                         |
| `anthropic` (official Python SDK) | Claude API access                               |
| `python-dotenv`                   | Loads `.env` into environment variables         |
| Windows Task Scheduler            | OS-level scheduling (no Python dependency)      |
| SMTP-capable email account        | Outbound mail (e.g. Gmail with an App Password) |
| Anthropic API key                 | Required credential                             |

No database, no web framework, no message queue, no containerization
needed for this scope.

## 7. Key Conventions

- **`.env` for all secrets.** Never hardcode API keys, passwords, or email
  addresses in source files. `.env` is gitignored; `.env.example` ships
  with blank values as a template for whoever sets this up next.
- **`NO_UPDATE` sentinel.** Any prompt can opt into "only email me if
  there's something to report" by instructing the model to respond with
  the exact string `NO_UPDATE` when there's nothing new. `runner.py`
  checks for this prefix and skips the email (but still logs and saves
  the output) when present. This keeps the "what counts as noteworthy"
  logic in the prompt text, not in Python.
- **One prompt file per distinct job.** Don't overload a single prompt
  file with multiple unrelated tasks - see Section 8 for how multiple
  prompts are intended to scale.

## 8. Planned Extension Points (Not Built Initially)

These are documented so a future developer understands the intended
growth path and doesn't need to redesign the architecture to support
them:

- **Multiple prompts, independent schedules.** `runner.py` should accept
  the prompt file path as a command-line argument (defaulting to
  `prompts/prompt_current.txt` if omitted), and output filenames should
  incorporate the prompt name, not just the date, so same-day runs from
  different prompts don't collide. Each schedule (daily/weekly/monthly)
  becomes its own Task Scheduler task pointing at its own prompt file.
- **Multiple prompts per single schedule.** A `.bat` file (or a single
  Task Scheduler task with multiple actions) can invoke `runner.py`
  multiple times in sequence, once per prompt file. No changes to
  `runner.py` itself are required for this - each invocation remains a
  fully independent, stateless run.
- **Live web access.** Prompts that reference URLs or need current
  information require the web-search tool to be added to the API call in
  `llm_client.py`. Without it, such prompts will be answered from the
  model's training data, which may be stale.
- **Reading email (IMAP).** Any prompt requiring inbox content (e.g. "summarize
  yesterday's emails") needs a new IMAP-ingestion module. This is a
  materially larger addition than the scheduling changes above and should
  be scoped as its own phase.
- **Combined/digest emails.** If multiple prompts run on one schedule and
  separate emails become undesirable, `runner.py` would need to be
  refactored to batch multiple prompt/response pairs into a single email
  send, rather than one send per prompt.

## 9. Suggested Build Phases

1. **Phase 1 - Core loop.** Build all five files above for a single
   prompt. Test manually (`python runner.py`) until a real email arrives
   correctly. Then schedule it and confirm at least one successful
   unattended run before considering it done.
2. **Phase 2 - Multiple schedules.** Add the CLI-argument support for
   prompt file selection. Create additional prompt files and additional
   scheduled tasks, each on its own cadence. Test and confirm each
   independently.
3. **Phase 3 - Multiple prompts per schedule.** Chain multiple `runner.py`
   invocations within a single `.bat` file or Task Scheduler task. No
   Python changes required.

## 10. Security Notes for Whoever Builds This

- Store the API key and email password only in `.env`; verify `.env` is
  in `.gitignore` _before_ the first `git add`, not after.
- Use an app-specific password for the sending email account rather than
  the account's main password, if the provider supports it (e.g. Gmail
  App Passwords).
- If flipping a repository containing this code from private to public,
  check the full git history for accidental secret commits first -
  removing a file in a later commit does not remove it from history.
