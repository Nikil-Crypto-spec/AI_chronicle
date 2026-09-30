# Weekly Scientific Newsletter Generator

A small local Python tool that, on demand, pulls the last 7 days of articles
from a configured set of scientific publishers (Nature, Science, arXiv, eLife,
PNAS, ...), ranks them against your topics of interest, summarises the top
items with a pluggable LLM backend (a local model via Ollama, or Microsoft
Copilot via Azure OpenAI), renders one HTML email, and sends it via SMTP.

Designed for a single user, run manually, on a Windows or Unix laptop. No
scheduler, no cloud, no container - just `run.cmd` (or `python run.py`).

---

## Table of contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Configure](#configure)
5. [Run it](#run-it)
6. [Choose an LLM backend](#choose-an-llm-backend)
7. [Send real email](#send-real-email)
8. [Corporate networks (SSL / CA)](#corporate-networks-ssl--ca)
9. [Project layout](#project-layout)
10. [Troubleshooting](#troubleshooting)

---

## How it works

```
sources.yaml + topics.yaml
        |
        v
  collectors  --(RSS / HTML)-->  RawItems
        |
        v
  freshness + seen-URL filter (SQLite state)
        |
        v
  cross-source dedupe (canonical URL + fuzzy title)
        |
        v
  ranker (keywords; optional embeddings)
        |
        v
  top N items  -->  optional full-text fetch
        |
        v
  summariser  -->  LLMClient (LocalLLM | CopilotLLM)
        |
        v
  Jinja2 HTML template
        |
        v
  sender (SMTP)  OR  --dry-run -> out\newsletter-YYYY-MM-DD.html
```

Each weekly run is idempotent: items already sent are remembered in
`state.sqlite` so you don't get the same paper twice.

---

## Prerequisites

- **Python 3.10+** (3.11 tested) on PATH.
- **Git** to clone the repo.
- *(Optional)* **[Ollama](https://ollama.com)** if you want local LLM
  summaries. Without it, the tool gracefully falls back to the article's
  abstract.
- *(Optional)* SMTP credentials (Outlook/Office365, Gmail with an app
  password, etc.) if you want the email actually sent. Otherwise, use
  `--dry-run` and view the rendered HTML in `out\`.

---

## Setup

```bash
git clone <repo-url> newsletter_generator
cd newsletter_generator

# Create a venv and install the project + dependencies (editable).
python -m venv .venv

# Windows (CMD):
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .

# macOS / Linux:
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

You do not need to "activate" the venv - the helper scripts (`run.cmd`,
`run.ps1`) call `.venv\Scripts\python.exe` directly, which sidesteps any
PowerShell execution-policy problems on locked-down machines.

---

## Configure

Three places to edit, in order of importance.

### 1. `.env` - secrets and toggles

Copy the template and edit:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Minimum to get going (everything else can stay default):

```ini
# Choose the LLM backend.
LLM_BACKEND=local

# If you're behind a corporate TLS-inspecting proxy and don't have your
# CA bundle handy, this gets you past it. See "Corporate networks" below
# for the proper fix.
INSECURE_SSL=true
```

Other knobs (all in `.env.example`):

| Variable | What it does |
| --- | --- |
| `LLM_BACKEND` | `local` (Ollama) or `copilot` (Azure OpenAI) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Local LLM endpoint and model name |
| `COPILOT_ENDPOINT` / `COPILOT_API_KEY` / `COPILOT_DEPLOYMENT` / `COPILOT_API_VERSION` | Azure OpenAI configuration |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `EMAIL_FROM` / `EMAIL_TO` | Email sending |
| `MAX_ITEMS` | Cap on items in the newsletter (default 12) |
| `SINCE_DAYS` | Look-back window in days (default 7) |
| `RANKING_USE_EMBEDDINGS` | Set to `true` for semantic rerank (requires the `embeddings` extra; see below) |
| `CA_BUNDLE` | Path to a PEM file with corporate root CAs |
| `INSECURE_SSL` | Disable TLS verification globally (escape hatch) |

`.env` is git-ignored; you won't accidentally commit secrets.

### 2. `config/topics.yaml` - what you care about

This is the single biggest lever on output quality. Replace the placeholder
topics with your real interests. Each topic has:

- `keywords` - matched as whole words in title + abstract.
- `phrases` - matched as substrings (case-insensitive); count more than
  single keywords.
- `weight` - scales the topic's contribution to the score.
- `seed_sentences` - natural-language descriptions used **only** if you
  enable embedding-based ranking.

There's also a `penalties` block to demote things you want to skip
(e.g. `retraction`, `errata`).

### 3. `config/sources.yaml` - which publishers to pull

Each source declares:

- `kind: rss` or `kind: html` (RSS strongly preferred; HTML is for sites with
  no feed).
- `url` - the feed URL (rss) or homepage URL (html).
- `weight` - per-source score multiplier.
- `enabled: true|false` - flip without deleting.

Adding/removing a source is a config change, not a code change. The seed
file already has Nature, Nature News, Science, arXiv (cs.LG), eLife, PNAS.
Disable what you don't want, add more as needed.

### 4. *(optional)* `config/prompts.yaml`

The summariser prompts. Edit only if you want a different tone or output
shape - the default produces strict JSON with `tldr`, `why_it_matters`, and
2-4 `key_points`.

---

## Run it

### Easiest: the wrapper scripts

```powershell
# Windows (CMD or PowerShell, regardless of execution policy):
.\run.cmd

# PowerShell, if execution policy allows .ps1:
.\run.ps1
```

`run.cmd` defaults to `--dry-run`, so it writes the rendered HTML to
`out\newsletter-YYYY-MM-DD.html` and opens it in your default browser
instead of sending email. Use it freely while iterating on topics/sources.

Useful flags (all forwarded straight to `run.py`):

```powershell
.\run.cmd --no-open                          # don't auto-open the HTML
.\run.cmd --since 14 --max-items 20          # bigger window, more items
.\run.cmd --no-enrich                        # skip article-body fetches (faster)
.\run.cmd --no-state                         # ignore previously-seen URLs (for iteration)
.\run.cmd --llm copilot                      # override LLM_BACKEND for this run
.\run.cmd --live                             # actually send email (drops --dry-run)
```

### Or call Python directly

```bash
.venv\Scripts\python.exe run.py --dry-run    # Windows
.venv/bin/python run.py --dry-run            # macOS / Linux
```

All flags from `--help`:

```
--since N            Look-back window in days (default: SINCE_DAYS or 7)
--max-items N        Cap on items in the newsletter (default: MAX_ITEMS or 12)
--llm local|copilot  Override LLM_BACKEND
--dry-run            Write HTML to out\ instead of sending email
--no-enrich          Skip full-text fetching even when abstracts are short
--no-state           Ignore seen_urls (don't filter, don't persist)
--sources-file PATH  Use a different sources.yaml (handy for tests)
```

### What you'll see

- Console: per-source RSS fetch counts, dedupe + ranking numbers, per-item
  LLM call status, and a final `Run done: N items sent, runtime Xs`.
- File: `out\newsletter-YYYY-MM-DD.html` (when `--dry-run`).
- Logs: `logs\run.log` (rotating, 5 MB).
- State: `state.sqlite` - tracks which URLs have already been sent so the
  next weekly run won't repeat them.

---

## Choose an LLM backend

The pipeline doesn't care which backend it talks to; one tiny adapter
implements `LLMClient.complete(system, user, ...) -> str`.

### Local (default) - Ollama

Free, private, no egress for article text.

1. Install Ollama from <https://ollama.com>.
2. Pull a model:
   ```powershell
   ollama pull llama3.1:8b-instruct-q4_K_M
   # or a smaller alternative:
   ollama pull qwen2.5:7b-instruct
   ```
3. Make sure Ollama is running (it auto-starts the service on Windows after
   install).
4. In `.env`:
   ```ini
   LLM_BACKEND=local
   OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
   ```
5. Run as normal. You'll see `Summarised N items (0 fallback, N via LLM)`.

If Ollama is unreachable, the summariser falls back to the article's
abstract automatically - the newsletter still gets produced.

### Copilot - Azure OpenAI

The `CopilotLLM` adapter targets an **Azure OpenAI** chat-completions
deployment in your Microsoft tenant.

1. From the Azure portal, get:
   - your resource endpoint, e.g. `https://my-resource.openai.azure.com`,
   - an API key,
   - your deployment name (e.g. `gpt-4o-mini`).
2. In `.env`:
   ```ini
   LLM_BACKEND=copilot
   COPILOT_ENDPOINT=https://my-resource.openai.azure.com
   COPILOT_API_KEY=...
   COPILOT_DEPLOYMENT=gpt-4o-mini
   COPILOT_API_VERSION=2024-06-01
   ```
3. Run with `.\run.cmd --llm copilot` (or just leave `LLM_BACKEND=copilot`
   in `.env`).

If your "Copilot" turns out to be a different Microsoft endpoint (GitHub
Copilot Chat, M365 Copilot), only [`newsletter/llm/copilot.py`](newsletter/llm/copilot.py)
needs to change - the rest of the pipeline only depends on the
`LLMClient` protocol.

### Optional: embedding-based ranking

By default, ranking uses keyword counts only. To add a semantic rerank
that compares each item against your topic seed sentences:

```bash
.venv\Scripts\python.exe -m pip install -e ".[embeddings]"
```

Then in `.env`:

```ini
RANKING_USE_EMBEDDINGS=true
```

First run will download a small `all-MiniLM-L6-v2` model (~80 MB).

---

## Send real email

Fill in the SMTP block in `.env`:

```ini
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=you@company.com
SMTP_PASSWORD=<app password>
EMAIL_FROM=you@company.com
EMAIL_TO=you@company.com
```

Then drop `--dry-run`:

```powershell
.\run.cmd --live
```

A few notes:
- For Office365 with MFA, you'll need an **app password** (or, separately,
  enable SMTP AUTH for the mailbox).
- Gmail requires an app password too (regular passwords don't work).
- If sending fails, the run falls back to writing the HTML to `out\` and
  records a row in `run_history` with the error - so you don't lose the
  newsletter.

---

## Corporate networks (SSL / CA)

If you see `CERTIFICATE_VERIFY_FAILED` on RSS fetches, your Python install
doesn't trust your corporate TLS-inspecting proxy. Two paths, in order of
preference:

### Proper fix: point at your CA bundle

```ini
CA_BUNDLE=C:\Users\<you>\corp-ca.pem
```

Get the PEM from your IT team, or export from Windows' cert store
(`certmgr.msc` -> Trusted Root CAs -> your corp CA -> All Tasks -> Export
as Base-64 .cer, rename to `.pem`). The tool sets
`SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` and reconfigures urllib's default
HTTPS context, so feedparser, httpx, **and** the Azure OpenAI client all
pick it up.

### Escape hatch: disable verification

```ini
INSECURE_SSL=true
```

Logs a loud warning and turns off cert verification globally. Don't leave
this on; use only when you have nothing else.

---

## Project layout

```
newsletter_generator/
  run.py                    # single Python entry point (CLI)
  run.cmd                   # Windows wrapper (CMD; bypasses PS execution policy)
  run.ps1                   # PowerShell wrapper
  pyproject.toml            # package metadata + dependencies
  .env.example              # env-var template (copy to .env)
  config/
    sources.yaml            # which publishers to pull
    topics.yaml             # what you care about
    prompts.yaml            # summariser prompts
  newsletter/
    config.py               # pydantic-settings + YAML loaders
    state.py                # SQLite (seen_urls, run_history)
    logging_setup.py        # rich console + rotating file handler
    models.py               # RawItem / RankedItem / SummarisedItem
    ssl_compat.py           # CA_BUNDLE / INSECURE_SSL plumbing
    collectors/
      base.py               # Collector ABC
      rss.py                # feedparser-based collector
      html.py               # httpx + BeautifulSoup collector
      registry.py           # rss|html -> collector class
    dedupe.py               # canonical URL + rapidfuzz title match
    ranking.py              # keyword scoring (+ optional embedding rerank)
    fulltext.py             # polite article-body fetch + readability extract
    llm/
      base.py               # LLMClient protocol
      local.py              # LocalLLM (Ollama)
      copilot.py            # CopilotLLM (Azure OpenAI)
      factory.py            # backend selector
    summariser.py           # LLM call + JSON parsing + abstract fallback
    formatter.py            # Jinja2 -> HTML body
    sender.py               # SMTP send / disk dry-run
  templates/
    newsletter.html.j2      # email template
  tools/
    smoke_test_offline.py   # pipeline test, no network needed
  out/                      # rendered newsletters land here in --dry-run
  logs/                     # rotating run.log
  state.sqlite              # created on first run; tracks seen URLs
```

---

## Troubleshooting

**PowerShell: "running scripts is disabled on this system"**
Your corporate group policy blocks `.ps1` files. Use `run.cmd` instead -
`.cmd` files aren't subject to PowerShell's execution policy. If you must
use `run.ps1`:
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

**`CERTIFICATE_VERIFY_FAILED` on RSS fetch**
See [Corporate networks](#corporate-networks-ssl--ca). Set `CA_BUNDLE` or
flip `INSECURE_SSL=true` in `.env`.

**`No connection could be made` from the LLM call**
Ollama isn't running. Either start it, or accept the abstract-fallback path
(the newsletter still gets produced; you'll just see "N fallback, 0 via
LLM" in the summary line).

**"Cannot send email; missing settings: ..."**
You ran without `--dry-run` but didn't fill in the SMTP block in `.env`.
Either fill them in, or use `.\run.cmd` (which defaults to `--dry-run`).

**The newsletter is empty / no items survived ranking**
Either your `topics.yaml` keywords don't match anything in the current
window, or `state.sqlite` already saw all the URLs. Try:
```powershell
.\run.cmd --since 14 --no-state
```

**I want to see the pipeline work without any network at all**
```bash
.venv\Scripts\python.exe tools\smoke_test_offline.py
```
Builds synthetic items in-memory, exercises dedupe -> rank -> summarise
(with a stub LLM that always raises, so you hit the fallback path) ->
formatter -> dry-run write. Useful as a sanity check after edits.

---

## Roadmap (deferred by design)

The current scope is "manual local run". Easy bolt-ons later, all
unblocked because the core is a single idempotent script with explicit
state:

- Schedule via Windows Task Scheduler / cron.
- Add per-source HTML collectors with custom selectors for editorial
  signals ("featured", "most read").
- Multi-recipient routing.
- A small Streamlit/Flask UI for browsing past runs from `state.sqlite`.
"# AI_chronicle" 
