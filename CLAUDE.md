# ALMOND: Memory-Driven Deployment Assistant

## Architecture: Recursive Language Model (RLM)
- **Core Principle:** Treat `vault/history.txt` as a programmable state variable, not a context window.
- **Engine Logic:** Use programmatic slicing (Python `exec()`) to navigate 10M+ tokens of logs.
- **Search Tiers:** 1. Human History (Vault) 
  2. Synthetic Memory (AI_Fixes) 
  3. First-Principles Synthesis.

## Build Rules (Person 2: The Orchestrator)
- **Sandbox Isolation:** All `exec()` calls must occur in `core/repl_env.py` with zero network access.
- **Recursion Guard:** Maximum recursive depth is **3**.
- **Memory Management:** Do not stream raw intermediate log chunks into the main LLM context. Only return high-density deltas (Error signature, diffs, hypothesis).
- **Subsume & Specificity:** When updating `vault/ai_fixes.json`, longer (more specific) regex patterns override shorter ones.

## Commands
- **Test Engine:** `python main.py`
- **Check Cache:** `cat vault/ai_fixes.json`
- **Debug Logs:** `almond debug --logs <file>` (Person 3 Implementation)
