# CLAUDE.md — System Instructions for Claude Code

## Project: Almond — AI Deployment Sentinel

Almond is an AI agent built on the **Recursive Language Model (RLM)** architecture.
It treats historical engineering data as a massive, grep-optimizable environment
rather than a vector store.

**This is a cross-project, dynamic tool.** It is not tied to any specific project.
You point it at any repo, log directory, or config folder — the vault grows across
all of them, and the AI can trace patterns across every project in the vault.

## Architecture (3-Person Split)

```
vault/     → Person 1 (The Librarian): Memory Vault — data ingestion & storage
core/      → Person 2 (The Engineer):  RLM Engine — recursive loop & sandbox
cli/       → Person 3 (The Designer):  Interface — CLI, UI, live capture
```

## Key Principle: NO Vector DBs

The RLM paper identifies **"Context Rot"** as a failure mode of standard RAG.
Almond preserves full sequential causality:

- Data is **never chunked** into independent vectors
- All logs are stored as **contiguous, delimited blocks** in `vault/history.txt`
- The agent queries data via **Python code execution** (grep, slice, read_bytes)
- Data layout is optimized for **text-processing tools**, not embeddings

## Vault Layout

```
vault/
├── history.txt         ← Single append-only file (logs + PRs + git commits)
├── golden_snippets/    ← Curated verified configs/scripts
├── index.json          ← Byte-offset metadata index
└── ingest.py           ← Ingestion engine + scraping automation
```

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Conventions

- Timestamps: ISO-8601 with timezone (e.g. `2025-01-15T10:30:00Z`)
- Delimiters: `--- START/END <TYPE> [timestamp] [project:X] [id:Y] ---`
- Tags: Freeform, colon-separated (e.g. `error:OOM`, `env:prod`, `type:fix`)
- Index: Byte offsets for seek-based access (no full-file loads)
- Projects: Dynamic — any string, no hardcoded project list
