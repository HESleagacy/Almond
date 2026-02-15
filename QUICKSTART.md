# ALMOND Quick Start Guide 🚀

Complete guide to running the ALMOND project with all test cases and examples.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Environment Setup](#environment-setup)
4. [Initialize Vault](#initialize-vault)
5. [Running Tests](#running-tests)
6. [Using the CLI](#using-the-cli)
7. [Understanding Output](#understanding-output)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **Python 3.10+** (check with `python --version`)
- **pip** (Python package manager)
- **Git** (for version control)

### Required Accounts
- **Anthropic API Key** - Get from [console.anthropic.com](https://console.anthropic.com)

---

## Installation

### Step 1: Navigate to Project Directory
```bash
cd /Users/abjt/Desktop/lunn/almond-cld/almond
```

### Step 2: Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
# .venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
# Install all dependencies
pip install -r requirements.txt

# Install ALMOND in editable mode
pip install -e .
```

### Step 4: Verify Installation
```bash
# Check that almond command is available
almond --help

# Should show:
# Usage: almond [OPTIONS] COMMAND [ARGS]...
# ALMOND: Memory-Driven Deployment Assistant...
```

---

## Environment Setup

### Step 1: Create `.env` File
```bash
# Create .env file in project root
cat > .env <<EOF
# Anthropic API Configuration
ANTHROPIC_API_KEY=your-api-key-here

# Vault Configuration
VAULT_PATH=./vault/history.txt
CACHE_PATH=./vault/ai_fixes.json

# Model Configuration (Optional)
ROOT_MODEL=claude-3-5-haiku-20241022
SUB_MODEL=claude-3-5-haiku-20241022
MAX_RECURSION_DEPTH=3
EOF
```

### Step 2: Add Your API Key
```bash
# Edit .env and replace with your actual API key
nano .env
# or
vim .env
# or
code .env  # VS Code
```

**Important:** Get your API key from [console.anthropic.com](https://console.anthropic.com/settings/keys)

### Step 3: Verify Environment Variables
```bash
# Check that .env is loaded
cat .env
```

---

## Initialize Vault

The vault stores historical error solutions. Let's create sample data:

### Step 1: Create Vault Directory
```bash
mkdir -p vault
```

### Step 2: Create Sample History File
```bash
cat > vault/history.txt <<'EOF'
# ALMOND Vault - Human-Solved Error History
# Format: Each entry documents a real deployment error and its solution

=== ENTRY 001: Kubernetes Pod CrashLoopBackOff ===
Date: 2024-01-15
Error: Pod nginx-deployment-abc123 in CrashLoopBackOff
Symptoms:
  - Error: Back-off restarting failed container
  - Events show "CrashLoopBackOff"
  - Container exits immediately after start

Root Cause: Missing environment variable DATABASE_URL

Solution:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DATABASE_URL: "postgresql://db:5432/app"
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        envFrom:
        - configMapRef:
            name: app-config
```

Outcome: Pod started successfully after applying ConfigMap

=== ENTRY 002: Docker Build Network Timeout ===
Date: 2024-01-20
Error: ERROR [internal] load metadata for docker.io/library/node:18
Symptoms:
  - Docker build hangs at "load metadata"
  - Timeout after 30 seconds
  - Error: dial tcp: lookup registry-1.docker.io: no such host

Root Cause: Docker daemon network configuration issue

Solution:
```bash
# Fix DNS in Docker daemon
sudo tee /etc/docker/daemon.json <<EOF
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF

# Restart Docker
sudo systemctl restart docker

# Retry build
docker build -t myapp .
```

Outcome: Build completed successfully

=== ENTRY 003: Connection Timeout to Database ===
Date: 2024-02-01
Error: ConnectionTimeout: Target 10.0.0.5:5432 unreachable after 30s
Symptoms:
  - Application logs show "connection timeout"
  - Database is running but unreachable
  - Network connectivity seems fine

Root Cause: Firewall blocking port 5432

Solution:
```bash
# Check firewall rules
sudo iptables -L -n

# Allow port 5432
sudo iptables -A INPUT -p tcp --dport 5432 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --sport 5432 -j ACCEPT

# Save rules
sudo iptables-save > /etc/iptables/rules.v4

# Verify connection
nc -zv 10.0.0.5 5432
```

Outcome: Connection established, application running

=== ENTRY 004: Out of Memory Error ===
Date: 2024-02-05
Error: OOMKilled - Container memory limit exceeded
Symptoms:
  - Pod terminated with exit code 137
  - Events show "OOMKilled"
  - Container using more memory than limit

Root Cause: Memory limit too low for workload

Solution:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: memory-demo
spec:
  containers:
  - name: app
    resources:
      requests:
        memory: "256Mi"
      limits:
        memory: "512Mi"  # Increased from 256Mi
```

Outcome: Pod running stably with adequate memory
EOF
```

### Step 3: Create Initial Cache File
```bash
cat > vault/ai_fixes.json <<'EOF'
[
  {
    "id": "fix-001",
    "error_signature": "CrashLoopBackOff.*missing.*variable",
    "fix_description": "Add missing environment variable to deployment",
    "fix_code": "kubectl set env deployment/<name> VAR_NAME=value",
    "confidence": 0.85,
    "hit_count": 5,
    "created_at": "2024-01-15T10:00:00Z",
    "last_used": "2024-02-10T15:30:00Z"
  },
  {
    "id": "fix-002",
    "error_signature": "ConnectionTimeout.*unreachable",
    "fix_description": "Check firewall rules and network connectivity",
    "fix_code": "# Check firewall\nsudo iptables -L\n# Allow port\nsudo iptables -A INPUT -p tcp --dport <port> -j ACCEPT",
    "confidence": 0.90,
    "hit_count": 12,
    "created_at": "2024-02-01T09:00:00Z",
    "last_used": "2024-02-14T11:20:00Z"
  },
  {
    "id": "fix-003",
    "error_signature": "OOMKilled.*137",
    "fix_description": "Increase memory limits in pod specification",
    "fix_code": "resources:\n  limits:\n    memory: \"512Mi\"\n  requests:\n    memory: \"256Mi\"",
    "confidence": 0.95,
    "hit_count": 8,
    "created_at": "2024-02-05T14:00:00Z",
    "last_used": "2024-02-13T16:45:00Z"
  }
]
EOF
```

### Step 4: Verify Vault Setup
```bash
# Check that files exist
ls -lh vault/

# Should show:
# history.txt
# ai_fixes.json
```

---

## Running Tests

### Run All Tests
```bash
# Run all tests with verbose output
pytest -v

# Expected output:
# ====== test session starts ======
# tests/cli/test_display.py::... PASSED
# tests/cli/test_formatters.py::... PASSED
# tests/cli/test_main.py::... PASSED
# tests/cli/test_utils.py::... PASSED
# ====== 78 passed in X.XXs ======
```

### Run Specific Test Suites

#### CLI Tests Only
```bash
pytest tests/cli/ -v
```

#### Display Component Tests
```bash
pytest tests/cli/test_display.py -v
```

#### Formatter Tests
```bash
pytest tests/cli/test_formatters.py -v
```

#### Main CLI Tests
```bash
pytest tests/cli/test_main.py -v
```

#### Utility Tests
```bash
pytest tests/cli/test_utils.py -v
```

### Run Tests with Coverage
```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage report
pytest --cov=cli --cov=core tests/ -v

# Generate HTML coverage report
pytest --cov=cli --cov=core tests/ --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test
```bash
# Run a single test by name
pytest tests/cli/test_display.py::TestStatusDisplay::test_resolved_by_vault -v
```

---

## Using the CLI

### Example 1: Diagnose Connection Timeout (Tier 2: Cache Hit)

#### Create Error Log
```bash
cat > error1.log <<EOF
[2024-02-15 10:30:45] ERROR: Connection failed
[2024-02-15 10:30:45] ConnectionTimeout: Target 10.0.0.5:8080 unreachable after 30s
[2024-02-15 10:30:45] Retrying connection... (attempt 1/3)
[2024-02-15 10:30:50] ConnectionTimeout: Target 10.0.0.5:8080 unreachable after 30s
[2024-02-15 10:30:50] Retrying connection... (attempt 2/3)
[2024-02-15 10:30:55] ConnectionTimeout: Target 10.0.0.5:8080 unreachable after 30s
[2024-02-15 10:30:55] Max retries exceeded. Exiting.
EOF
```

#### Run Diagnosis
```bash
almond debug --logs error1.log
```

**Expected Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Resolution Tier          ┃
┃   Tier 2: Synthetic Cache  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Confidence: [████████████████████████████░░] 90%

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Fix Description          ┃
┃   Check firewall rules and ┃
┃   network connectivity     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Fix Code                 ┃
┃   # Check firewall         ┃
┃   sudo iptables -L         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Example 2: Diagnose CrashLoopBackOff (Tier 1: Vault Match)

#### Create Error Log
```bash
cat > error2.log <<EOF
[2024-02-15 11:00:00] Pod nginx-deployment-xyz789 failed to start
[2024-02-15 11:00:00] Error: Back-off restarting failed container
[2024-02-15 11:00:05] Events: CrashLoopBackOff
[2024-02-15 11:00:05] Container exits immediately after start
[2024-02-15 11:00:10] Missing environment variable DATABASE_URL
EOF
```

#### Run Diagnosis
```bash
almond debug --logs error2.log
```

**Expected Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Resolution Tier          ┃
┃   Tier 1: Human History    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Root Cause               ┃
┃   Missing environment      ┃
┃   variable DATABASE_URL    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Solution                 ┃
┃   [YAML syntax highlighted]┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Example 3: Output Formats

#### JSON Format (for scripting)
```bash
almond debug --logs error1.log --format json
```

**Output:**
```json
{
  "status": "RESOLVED_BY_CACHE",
  "fix": {
    "id": "fix-002",
    "error_signature": "ConnectionTimeout.*unreachable",
    "fix_description": "Check firewall rules and network connectivity",
    "fix_code": "sudo iptables -L",
    "confidence": 0.90
  }
}
```

#### Minimal Format (for piping)
```bash
almond debug --logs error1.log --format minimal > fix.sh
cat fix.sh
```

**Output:**
```bash
# Check firewall
sudo iptables -L
# Allow port
sudo iptables -A INPUT -p tcp --dport <port> -j ACCEPT
```

#### Verbose Mode (with reasoning trace)
```bash
almond debug --logs error1.log --verbose
```

**Additional Output:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Reasoning Trace          ┃
┃                            ┃
┃   🔍 Depth 0: EXECUTE_CODE ┃
┃      Searching cache...    ┃
┃                            ┃
┃   ✓ Depth 0: FINAL_REPORT  ┃
┃      Cache hit found       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Example 4: Complex Error (Tier 3: Synthesis)

#### Create Complex Error
```bash
cat > error3.log <<EOF
[2024-02-15 12:00:00] FATAL: Unhandled exception in worker process
[2024-02-15 12:00:00] MemoryError: Unable to allocate 2.5 GiB
[2024-02-15 12:00:00] Stack trace:
[2024-02-15 12:00:00]   File "/app/main.py", line 42, in process_data
[2024-02-15 12:00:00]   File "/app/utils.py", line 156, in load_dataset
[2024-02-15 12:00:00] Last 10 operations: batch_size=10000, iterations=500
[2024-02-15 12:00:05] Worker crashed with exit code 139
EOF
```

#### Run Diagnosis with Verbose
```bash
almond debug --logs error3.log --verbose
```

This will trigger Tier 3 synthesis if no cache/vault match is found, showing:
- Root cause analysis
- Generated solution
- Full reasoning trace with depth levels

---

## Understanding Output

### Resolution Tiers

#### Tier 1: Human History (Green)
- **Source:** `vault/history.txt`
- **Fidelity:** Highest - Real human-solved incidents
- **Color:** Green border
- **Fields:** Root Cause + Solution

#### Tier 2: Synthetic Cache (Yellow)
- **Source:** `vault/ai_fixes.json`
- **Fidelity:** High - Previously AI-synthesized fixes
- **Color:** Yellow border
- **Fields:** Confidence + Description + Code

#### Tier 3: First-Principles Synthesis (Blue)
- **Source:** LLM generates fresh solution
- **Fidelity:** Variable - Depends on error complexity
- **Color:** Blue border
- **Fields:** Root Cause + Solution + Trace (if verbose)

### Confidence Levels

| Score | Color  | Meaning |
|-------|--------|---------|
| ≥80%  | Green  | High confidence - Safe to apply |
| 50-80%| Yellow | Medium confidence - Review first |
| <50%  | Red    | Low confidence - Manual review needed |

---

## Troubleshooting

### Problem: `almond: command not found`

**Solution:**
```bash
# Make sure you installed with -e flag
pip install -e .

# Verify installation
which almond

# If still not found, activate venv
source .venv/bin/activate
```

### Problem: `ANTHROPIC_API_KEY not set`

**Solution:**
```bash
# Check if .env exists
ls -la .env

# Export directly if needed
export ANTHROPIC_API_KEY="your-key-here"

# Or add to shell profile
echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### Problem: `Vault not found at ./vault/history.txt`

**Solution:**
```bash
# Create vault directory
mkdir -p vault

# Create empty history file
touch vault/history.txt
echo "# ALMOND Vault" > vault/history.txt

# Create empty cache
echo "[]" > vault/ai_fixes.json
```

### Problem: Tests failing

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Clear pytest cache
rm -rf .pytest_cache

# Run tests again
pytest -v
```

### Problem: Import errors

**Solution:**
```bash
# Make sure you're in the project root
pwd
# Should show: /Users/abjt/Desktop/lunn/almond-cld/almond

# Reinstall in editable mode
pip install -e .
```

---

## Quick Command Reference

```bash
# Installation
pip install -e .

# Run all tests
pytest -v

# CLI commands
almond --help
almond version
almond debug --logs <file>
almond debug -l <file> --format json
almond debug -l <file> --format minimal
almond debug -l <file> --verbose

# Environment
export ANTHROPIC_API_KEY="sk-ant-..."
export VAULT_PATH="./vault/history.txt"
export CACHE_PATH="./vault/ai_fixes.json"
```

---

## Next Steps

1. ✅ Install dependencies
2. ✅ Set up environment variables
3. ✅ Initialize vault with sample data
4. ✅ Run all tests
5. ✅ Try example error logs
6. 📚 Add your own error history to vault
7. 🚀 Use in production deployments

---

## Support

- **Documentation:** See `CLAUDE.md` for architecture
- **Implementation:** See `CLI_IMPLEMENTATION_SUMMARY.md` for details
- **Issues:** File at repository issue tracker
- **API Docs:** [docs.anthropic.com](https://docs.anthropic.com)

---

**Enjoy using ALMOND! 🌰**
