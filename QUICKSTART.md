# ALMOND Quick Start Guide

Get up and running with ALMOND in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- pip package manager
- Anthropic API key ([Get one here](https://console.anthropic.com/))

## Installation

### Step 1: Clone or Navigate to Project

```bash
cd /path/to/almond
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install ALMOND

```bash
pip install -e .
```

This will install ALMOND and all dependencies:
- anthropic (Claude API client)
- typer (CLI framework)
- rich (Terminal formatting)
- pytest (Testing)
- pyyaml (Configuration)
- python-dotenv (Environment variables)

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=your-api-key-here

# Optional: Custom paths (defaults shown)
VAULT_PATH=./vault/history.txt
CACHE_PATH=./vault/ai_fixes.json

# Optional: Model configuration
ROOT_MODEL=claude-3-5-haiku-20241022
SUB_MODEL=claude-3-5-haiku-20241022
MAX_RECURSION_DEPTH=3
```

Or export directly:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

## Verify Installation

Check that ALMOND is installed correctly:

```bash
almond --help
```

You should see the help menu with available commands.

```bash
almond version
```

You should see:
```
ALMOND RLM v0.1.0
Memory-Driven Deployment Assistant

Core Components:
  • Recursive Language Model (RLM) Engine
  • Three-tier search: Vault → Cache → Synthesis
  • Programmable memory with subsumption logic
```

## Your First Diagnosis

### Example 1: Connection Timeout

Diagnose a connection timeout error:

```bash
almond debug --logs examples/error1-connection-timeout.log
```

You'll see a beautifully formatted output with:
- Resolution tier (Vault/Cache/Synthesis)
- Confidence score
- Fix description
- Fix code (with syntax highlighting)

### Example 2: JSON Output

Get machine-readable output:

```bash
almond debug -l examples/error2-crashloop.log --format json
```

Perfect for piping to other tools:

```bash
almond debug -l error.log -f json | jq '.report.fix_code'
```

### Example 3: Minimal Output

Get just the fix for scripting:

```bash
almond debug -l examples/error3-oom.log --format minimal
```

Save to a file:

```bash
almond debug -l error.log -f minimal > fix.sh
bash fix.sh
```

### Example 4: Verbose Mode

See the reasoning trace:

```bash
almond debug -l examples/error1-connection-timeout.log --verbose
```

This shows the hierarchical reasoning tree of how ALMOND arrived at the solution.

## Understanding the Output

### Pretty Format (Default)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Resolution Tier          ┃
┃   Tier 2: Synthetic Cache  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Confidence: [████████████████████] 85%

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Fix Description          ┃
┃   Increase readiness probe ┃
┃   delay and memory limits  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Fix Code                 ┃
┃   readinessProbe:          ┃
┃     initialDelaySeconds:30 ┃
┃   resources:               ┃
┃     limits:                ┃
┃       memory: 512Mi        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Tier Colors

- **Green**: Tier 1 (Vault) - High-fidelity human-solved matches
- **Yellow**: Tier 2 (Cache) - Previously synthesized AI fixes
- **Blue**: Tier 3 (Synthesis) - First-principles LLM generation

### Confidence Scores

- **Green (≥80%)**: High confidence, safe to apply
- **Yellow (50-80%)**: Medium confidence, review recommended
- **Red (<50%)**: Low confidence, manual review required

## Common Use Cases

### Debugging Kubernetes Deployments

```bash
kubectl logs pod-name > error.log
almond debug -l error.log
```

### CI/CD Integration

```bash
# In your CI/CD pipeline
if ! kubectl rollout status deployment/myapp; then
  kubectl logs deployment/myapp > deploy-error.log
  almond debug -l deploy-error.log -f json > fix.json
  # Send fix.json to your incident management system
fi
```

### Batch Processing

```bash
# Diagnose multiple error logs
for log in logs/*.log; do
  echo "Analyzing $log..."
  almond debug -l "$log" -f minimal >> all-fixes.txt
done
```

## Running Tests

Verify everything works:

```bash
pytest -v
```

All 122 tests should pass:
- 78 CLI tests
- 44 Vault/Librarian tests

## Next Steps

1. **Populate the Vault**: Add your own deployment logs and PRs to `vault/history.txt`
2. **Build the Cache**: As you use ALMOND, the synthetic cache grows automatically
3. **Customize Models**: Adjust `ROOT_MODEL` and `SUB_MODEL` in `.env` for different Claude models
4. **Integrate**: Add ALMOND to your CI/CD pipeline for automatic error diagnosis

## Troubleshooting

### "Vault not found" Error

Make sure `vault/history.txt` exists. The project includes a sample vault with example entries.

### "API key not found" Error

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY='your-key-here'
```

Or add it to `.env` file.

### Import Errors

Make sure you installed in editable mode:

```bash
pip install -e .
```

### Command Not Found

Activate your virtual environment:

```bash
source venv/bin/activate
```

## Getting Help

- Run `almond --help` for command help
- Run `almond debug --help` for debug command options
- Check [README.md](README.md) for architecture details
- Check [CLI_IMPLEMENTATION_SUMMARY.md](CLI_IMPLEMENTATION_SUMMARY.md) for CLI details

## Example Workflow

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Get deployment logs
kubectl logs deployment/myapp > error.log

# 3. Diagnose with ALMOND
almond debug -l error.log

# 4. Review the fix

# 5. Apply the fix (if confident)
almond debug -l error.log -f minimal | kubectl apply -f -
```

Happy debugging!
