# 🌰 ALMOND: Memory-Driven Deployment Assistant

> **A**utomated **L**og **M**emory **O**rchestrator for **N**etwork **D**eployments

ALMOND uses Recursive Language Models (RLM) to diagnose deployment errors by searching through three tiers of memory: human-solved history, synthetic AI cache, and first-principles synthesis.

---

## 🚀 Quick Start

### 1. Install
```bash
# Install dependencies
pip install -r requirements.txt

# Install ALMOND
pip install -e .
```

### 2. Configure
```bash
# Copy example environment file
cp .env.example .env

# Add your Anthropic API key
echo "ANTHROPIC_API_KEY=your-key-here" >> .env
```

### 3. Run
```bash
# Diagnose an error
almond debug --logs examples/error1-connection-timeout.log

# See all options
almond --help
```

---

## 📊 Project Status

✅ **Implementation: Complete**
- ✅ RLM Engine (Recursive Language Model)
- ✅ CLI Interface with Rich visualization
- ✅ Three-tier search system
- ✅ 122 passing tests

```bash
$ pytest -v
============================== 122 passed ==============================
```

---

## 🏗️ Architecture

### Three-Tier Search System

```
┌──────────────────────────────────────────────┐
│  Tier 1: Human History (vault/history.txt)  │
│  High-fidelity human-solved incidents       │
│  Color: Green                                │
└──────────────────────────────────────────────┘
                    ↓ no match
┌──────────────────────────────────────────────┐
│  Tier 2: Synthetic Cache (ai_fixes.json)    │
│  Previously AI-synthesized fixes             │
│  Color: Yellow                               │
└──────────────────────────────────────────────┘
                    ↓ no match
┌──────────────────────────────────────────────┐
│  Tier 3: First-Principles Synthesis          │
│  LLM generates fresh solution                │
│  Color: Blue                                 │
└──────────────────────────────────────────────┘
```

### Directory Structure

```
almond/
├── cli/              # CLI interface with Typer & Rich
│   ├── main.py       # Commands: debug, version
│   ├── display.py    # Display components
│   ├── formatters.py # Output formats (pretty, json, minimal)
│   └── utils.py      # File reading, validation
│
├── core/             # RLM Engine
│   ├── engine.py     # Three-tier search logic
│   ├── prompts.py    # System prompts
│   ├── repl_env.py   # Sandboxed code execution
│   └── tools.py      # Vault reader, cache manager
│
├── vault/            # Memory storage
│   ├── history.txt   # Human-solved history
│   ├── ai_fixes.json # Synthetic cache
│   └── ingest.py     # Log ingestion utilities
│
├── tests/            # Test suite (122 tests)
│   ├── cli/          # CLI tests (78 tests)
│   └── test_librarian.py  # Vault tests (44 tests)
│
└── examples/         # Sample error logs
    ├── error1-connection-timeout.log
    ├── error2-crashloop.log
    └── error3-oom.log
```

---

## 🎯 Features

### CLI Commands

#### `almond debug`
Diagnose deployment errors from log files.

```bash
# Basic usage
almond debug --logs error.log

# JSON output (for scripting)
almond debug -l error.log --format json

# Minimal output (for piping)
almond debug -l error.log -f minimal > fix.sh

# Verbose (show reasoning trace)
almond debug -l error.log --verbose
```

#### `almond version`
Show version and component information.

```bash
almond version
```

### Output Formats

| Format | Use Case | Example |
|--------|----------|---------|
| **pretty** | Terminal viewing | Rich panels with colors |
| **json** | Scripting/automation | Machine-readable JSON |
| **minimal** | Piping to files | Plain text fix code |

### Display Components

- **StatusDisplay**: Tier-specific colored panels
- **ConfidenceIndicator**: Progress bars (green ≥80%, yellow 50-80%, red <50%)
- **CodeExtractor**: Syntax highlighting (YAML, Python, Bash, Dockerfile, JSON)
- **TraceTreeBuilder**: Hierarchical reasoning visualization

---

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Complete setup and usage guide
- **[CLAUDE.md](CLAUDE.md)** - Architecture and build rules
- **[CLI_IMPLEMENTATION_SUMMARY.md](CLI_IMPLEMENTATION_SUMMARY.md)** - CLI details

---

## 🧪 Running Tests

### All Tests
```bash
pytest -v
```

### CLI Tests Only
```bash
pytest tests/cli/ -v
```

### Specific Component
```bash
pytest tests/cli/test_display.py -v
pytest tests/cli/test_formatters.py -v
pytest tests/cli/test_main.py -v
```

### With Coverage
```bash
pytest --cov=cli --cov=core tests/ -v
```

---

## 💡 Examples

### Example 1: Connection Timeout (Cache Hit)

```bash
$ almond debug --logs examples/error1-connection-timeout.log
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Resolution Tier          ┃
┃   Tier 2: Synthetic Cache  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Confidence: [████████████████████████████░░] 90%

Fix: Check firewall rules and network connectivity
Code: sudo iptables -L
```

### Example 2: CrashLoopBackOff (Vault Match)

```bash
$ almond debug --logs examples/error2-crashloop.log
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Resolution Tier          ┃
┃   Tier 1: Human History    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Root Cause: Missing environment variable DATABASE_URL
Solution: [YAML syntax highlighted ConfigMap]
```

### Example 3: JSON Output for Scripting

```bash
$ almond debug -l examples/error1-connection-timeout.log -f json | jq .
```

**Output:**
```json
{
  "status": "RESOLVED_BY_CACHE",
  "fix": {
    "error_signature": "ConnectionTimeout.*unreachable",
    "fix_description": "Check firewall rules",
    "fix_code": "sudo iptables -L",
    "confidence": 0.90
  }
}
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your-api-key-here

# Optional (with defaults)
VAULT_PATH=./vault/history.txt
CACHE_PATH=./vault/ai_fixes.json
ROOT_MODEL=claude-3-5-haiku-20241022
SUB_MODEL=claude-3-5-haiku-20241022
MAX_RECURSION_DEPTH=3
```

### Vault Setup

The vault stores historical error solutions:

```bash
# Vault is already initialized with sample data
cat vault/history.txt

# Add your own entries
vim vault/history.txt
```

---

## 🎓 How It Works

### RLM (Recursive Language Model)

ALMOND implements four core principles:

1. **Context-as-State**: Vault and cache are programmable state variables
2. **Parent-Child Recursion**: Root model for parents, sub-model for children
3. **Synthetic Memory**: Write-back with subsumption (longer patterns win)
4. **Delta Filtering**: Only compressed deltas flow between recursion levels

### Search Flow

```python
# Simplified engine logic
def debug(log_content):
    # Tier 1: Search human history
    if vault_match := search_vault(log_content):
        return synthesize_from_vault(vault_match)

    # Tier 2: Search synthetic cache
    if cache_hit := search_cache(log_content):
        return cache_hit

    # Tier 3: De novo synthesis
    return recursive_synthesis(log_content)
```

---

## 📈 Test Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| CLI Display | 33 | ✅ Passing |
| CLI Formatters | 17 | ✅ Passing |
| CLI Main | 17 | ✅ Passing |
| CLI Utils | 11 | ✅ Passing |
| Vault/Librarian | 44 | ✅ Passing |
| **Total** | **122** | **✅ 100%** |

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and install
git clone <repository>
cd almond
pip install -e .

# Run tests
pytest -v

# Run specific test
pytest tests/cli/test_display.py::TestStatusDisplay::test_resolved_by_vault -v
```

### Project Commands

```bash
# Install
pip install -e .

# Test
pytest -v
pytest tests/cli/ -v
pytest --cov=cli --cov=core tests/

# CLI
almond --help
almond version
almond debug --logs <file>
```

---

## 📝 License

See LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest -v`
5. Submit a pull request

---

## 📞 Support

- **Documentation**: See QUICKSTART.md for complete guide
- **Issues**: File at repository issue tracker
- **API**: [docs.anthropic.com](https://docs.anthropic.com)

---

**Built with Claude Sonnet 4.5** 🤖

*ALMOND: Making deployments less nutty, one error at a time.* 🌰
