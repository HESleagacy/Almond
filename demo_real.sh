#!/bin/bash
# ALMOND Real Demo Script
# Demonstrates:
# 1. Tier 1 Memory (Instant Recall of Legacy Bugs)
# 2. Tier 3 Synthesis (First-Principles Thinking for Novel Bugs)

set -e

echo "================================================================"
echo "  ALMOND: Real-World Capability Demo"
echo "================================================================"
echo ""

# Setup
echo "Creating demo environment..."
source venv/bin/activate
# export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"  <-- Removed, let .env handle it

echo ""
echo "----------------------------------------------------------------"
echo "DEMO 1: THE MEMORY TEST (Tier 1)"
echo "----------------------------------------------------------------"
echo "Scenario: "
echo "  A 'Protocol Mismatch' error occurs. This happened once before"
echo "  in 2025. Does ALMOND remember the fix immediately?"
echo ""
echo "Command: almond debug -l examples/tier1-legacy-memory.log"
echo ""

almond debug -l examples/tier1-legacy-memory.log --format pretty

echo ""
echo "RESULT CHECK:"
echo "  - Should be 'RESOLVED_BY_VAULT' (accessing 2025 history)"
echo "  - Should cite the config change: FORCE_V1_HANDSHAKE"
echo ""
echo "----------------------------------------------------------------"
echo "DEMO 2: THE CACHE TEST (Tier 2)"
echo "----------------------------------------------------------------"
echo "Scenario:"
echo "  A 'Connection Timeout' error occurs."
echo "  This exact issue was solved by AI earlier today (in ai_fixes.json)."
echo "  ALMOND should find the cached fix without re-synthesizing."
echo ""
echo "Command: almond debug -l examples/tier2-cached.log"
echo ""

almond debug -l examples/tier2-cached.log --format pretty

echo ""
echo "RESULT CHECK:"
echo "  - Should be 'RESOLVED_BY_CACHE' (Yellow)"
echo "  - Should cite 'Increase readinessProbe' fix"
echo ""
echo "----------------------------------------------------------------"
echo "DEMO 3: THE INTELLIGENCE TEST (Tier 3)"
echo "----------------------------------------------------------------"
echo "Scenario:"
echo "  A nasty 'Deadlock in Async Worker' appears. This is NEW."
echo "  It is NOT in the vault. ALMOND must deduce the fix."
echo ""
echo "Command: almond debug -l examples/tier3-novel-bug.log"
echo ""

almond debug -l examples/tier3-novel-bug.log --format pretty

echo ""
echo "RESULT CHECK:"
echo "  - Should be 'RESOLVED_BY_SYNTHESIS' (Blue)"
echo "  - Should show reasoning (EXECUTE_CODE -> RECURSE)"
echo ""
echo "================================================================"
echo "  DEMO COMPLETE"
echo "================================================================"
