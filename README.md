# Almond — AI Deployment Sentinel

An AI agent built on the **Recursive Language Model (RLM)** architecture. Instead of vector-based RAG, Almond treats historical engineering data as a massive, grep-optimizable environment that the LLM queries programmatically via a Python REPL.

> **No Vector DBs.** The RLM paper identifies "Context Rot" as a failure mode of standard RAG. Almond preserves full sequential causality.

## The Problem: Institutional Amnesia

You fix a `ResourceQuota` crash in Project A. Six months later, Project B fails with a generic `Timeout`. You spend 3 hours debugging — it's the same root cause. **Almond remembers what you don't.**

## How It Works

1. **Feed it data** — Point the Librarian at any repo, log directory, or config folder
2. **It builds a vault** — All data goes into a single, massive `history.txt` (the "State Variable")
3. **The AI searches it** — Instead of chunking + embeddings, the AI writes Python code to grep/slice the vault

This is a **cross-project tool**. Point it at 5 repos, 10 repos, or 50 — the vault grows, and the AI can trace patterns **across all of them**.

## Project Structure

```
├── vault/                 # 📚 THE "MEMORY" (Person 1: The Librarian)
│   ├── history.txt        # The massive state variable (Logs, PRs, Git commits)
│   ├── golden_snippets/   # Curated configs & scripts that actually worked
│   ├── index.json         # Byte-offset metadata for fast seeking
│   └── ingest.py          # Ingestion engine + scraping automation
├── core/                  # 🧠 THE RLM ENGINE (Person 2: The Engineer)
│   ├── engine.py          # Main RLM Controller
│   ├── repl_env.py        # Sandboxed Python REPL
│   ├── tools.py           # Tools the AI calls: grep, slice, sub_query
│   └── prompts.py         # System prompts
├── cli/                   # 🛠 THE INTERFACE (Person 3: The Designer)
│   ├── main.py            # CLI Entry point
│   ├── formatter.py       # "Thought Trace" UI
│   └── capture.py         # Live deployment capture
├── config/settings.yaml
├── requirements.txt
└── .env
```

## Quick Start

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Feeding the Vault (Person 1's API)

```python
from vault.ingest import Librarian

lib = Librarian("./vault")

# ── Scrape any git repo ──────────────────────────────────────────
lib.scrape_git_log("~/code/project-alpha", project="project-alpha")
lib.scrape_git_log("~/code/project-beta",  project="project-beta")
lib.scrape_git_log("~/work/infra-monorepo", project="infra", since="2024-06-01")

# ── Scrape deployment/CI log directories ─────────────────────────
lib.scrape_log_directory("/var/log/deploys/", project="prod-cluster")
lib.scrape_log_directory("~/ci-outputs/", project="ci-pipeline")

# ── Extract golden configs (Helm, Dockerfile, K8s, Terraform) ────
lib.extract_golden_snippets("~/code/project-alpha/deploy/", project="project-alpha")
lib.extract_golden_snippets("~/infra/charts/", project="helm-charts")

# ── Or ingest individual items manually ──────────────────────────
lib.ingest_deployment_log("any-project", open("crash.log").read(), tags=["env:prod"])
lib.ingest_pull_request("any-project", open("fix.diff").read(), pr_number=42)
lib.ingest_golden_code("any-project", open("nginx.conf").read(), language="nginx")
```

## Querying the Vault

```python
from core.tools import VaultReader

reader = VaultReader("./vault")

# Search ACROSS all projects
reader.grep(r"OOM|ResourceQuota|memory")

# Search within a specific project
reader.grep(r"timeout", project="project-alpha")

# Time-based retrieval
reader.get_log_window("2025-01-15T10:30:00Z", window_size=3600)

# Byte-range slice (for massive files)
reader.read_bytes("vault/history.txt", start=0, end=4096)

# Drill into a specific entry
reader.sub_query("project-alpha", "entry-id", "ERROR")
```

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
