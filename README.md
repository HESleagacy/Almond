# ALMOND: Memory-Driven Deployment Assistant

**ALMOND** (Adaptive Learning Memory for Operational Network Diagnostics) is an AI-powered deployment assistant that uses Recursive Language Models (RLM) to diagnose and fix deployment errors by learning from historical data.

## Overview

ALMOND revolutionizes deployment debugging by treating your deployment history as a programmable state variable, not just a context window. It can search through millions of tokens of historical logs programmatically to find solutions to deployment errors.

## Architecture: Recursive Language Model (RLM)

ALMOND uses a three-tier search system:

1. **Tier 1: Human History (Vault)** - High-fidelity matches from human-solved deployment logs and pull requests
2. **Tier 2: Synthetic Cache (AI Fixes)** - Previously synthesized AI fixes with confidence scores
3. **Tier 3: First-Principles Synthesis** - LLM generates and validates solutions from scratch

### Core Principles

- **Context-as-State**: Treat `vault/history.txt` as a programmable state variable
- **Programmatic Search**: Use Python `exec()` to navigate 10M+ tokens of logs efficiently
- **Sandbox Isolation**: All code execution occurs in isolated `core/repl_env.py` with zero network access
- **Recursion Guard**: Maximum recursive depth of 3 to prevent infinite loops
- **Memory Management**: Only high-density deltas are returned to the main LLM context
- **Subsume & Specificity**: Longer, more specific regex patterns override shorter ones in the cache

## Features

- **Multi-Format Output**: Pretty (colored terminal), JSON (machine-readable), or minimal (plain text)
- **Tier Visualization**: Color-coded results by search tier (Green=Vault, Yellow=Cache, Blue=Synthesis)
- **Syntax Highlighting**: Auto-detected language support for fix code
- **Trace Visualization**: Hierarchical reasoning tree in verbose mode
- **Confidence Scoring**: Visual confidence indicators for AI-generated fixes
- **Learning Loop**: Accepted fixes update the synthetic cache with increased confidence

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

```bash
# Install
pip install -e .

# Set API key
export ANTHROPIC_API_KEY='your-key-here'

# Diagnose an error
almond debug --logs error.log

# Get JSON output
almond debug -l error.log --format json

# Get minimal output (for scripting)
almond debug -l error.log --format minimal > fix.sh
```

## Commands

### `almond debug`

Diagnose deployment errors using the RLM engine.

**Options:**
- `--logs, -l`: Path to log file (required)
- `--format, -f`: Output format: `pretty` (default), `json`, or `minimal`
- `--verbose, -v`: Show detailed reasoning trace
- `--context, -c`: Number of characters around error signature (default: 500)

**Examples:**
```bash
almond debug --logs examples/error1-connection-timeout.log
almond debug -l error.log --format json | jq .
almond debug -l error.log --verbose
almond debug -l error.log -f minimal > fix.sh && bash fix.sh
```

### `almond version`

Show version information and core components.

## Project Structure

```
almond/
├── cli/              # CLI interface (Typer-based)
│   ├── main.py       # Command definitions
│   ├── display.py    # Rich display components
│   ├── formatters.py # Output formatters
│   └── utils.py      # Utility functions
├── core/             # RLM engine
│   ├── engine.py     # Main RLM engine
│   ├── prompts.py    # System prompts
│   ├── repl_env.py   # Sandboxed execution environment
│   └── tools.py      # Vault reader tools
├── vault/            # Memory storage
│   ├── ingest.py     # Librarian for ingesting logs
│   ├── history.txt   # Deployment logs and PRs
│   └── ai_fixes.json # Synthetic cache
├── tests/            # Test suite (122 tests)
└── examples/         # Example error logs
```

## Environment Variables

**Required:**
- `ANTHROPIC_API_KEY` - Your Claude API key

**Optional (with defaults):**
- `VAULT_PATH` - Path to vault history (default: `./vault/history.txt`)
- `CACHE_PATH` - Path to AI fixes cache (default: `./vault/ai_fixes.json`)
- `ROOT_MODEL` - Parent model (default: `claude-3-5-haiku-20241022`)
- `SUB_MODEL` - Child model (default: `claude-3-5-haiku-20241022`)
- `MAX_RECURSION_DEPTH` - Max recursion depth (default: `3`)

## How It Works

1. **Ingest**: Historical deployment logs, PRs, and fixes are ingested into the vault
2. **Search**: When an error occurs, ALMOND searches through three tiers
3. **Match**: High-confidence matches from vault or cache are returned immediately
4. **Synthesize**: If no match found, LLM generates a fix from first principles
5. **Learn**: Accepted fixes are added to the synthetic cache for future use

## Build Rules

- **Sandbox Isolation**: All `exec()` calls occur in `core/repl_env.py` with zero network access
- **Recursion Guard**: Maximum recursive depth is 3
- **Memory Management**: No raw log chunks in main LLM context, only high-density deltas
- **Subsume Logic**: Longer regex patterns override shorter ones in cache updates

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please ensure all tests pass before submitting PRs.

```bash
pytest -v
```

## Support

For issues or questions, please open an issue on GitHub.
