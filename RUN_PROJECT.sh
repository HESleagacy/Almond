#!/bin/bash
# ALMOND Project - Complete Run Script
# This script demonstrates how to run the entire project with test cases

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════"
echo "  🌰 ALMOND: Memory-Driven Deployment Assistant"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Step 1: Check Python version
echo "📋 Step 1: Checking Python version..."
python --version
echo ""

# Step 2: Install dependencies
echo "📦 Step 2: Installing dependencies..."
pip install -q -e .
echo "✅ Installation complete"
echo ""

# Step 3: Verify CLI installation
echo "🔧 Step 3: Verifying CLI installation..."
almond --help
echo ""

# Step 4: Show version
echo "ℹ️  Step 4: Checking version..."
almond version
echo ""

# Step 5: Run all tests
echo "🧪 Step 5: Running all tests..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pytest -v --tb=short
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 6: Run CLI tests specifically
echo "🎯 Step 6: Running CLI tests..."
pytest tests/cli/ -v --tb=short
echo ""

# Step 7: Verify vault setup
echo "📚 Step 7: Verifying vault setup..."
echo "Vault history entries:"
grep -c "ENTRY" vault/history.txt || echo "0"
echo ""
echo "Cache fixes:"
cat vault/ai_fixes.json | python -m json.tool | grep '"id"' | wc -l
echo ""

# Step 8: Test with example error logs
echo "🔍 Step 8: Testing with example error logs..."
echo ""
echo "Example 1: Connection Timeout"
echo "────────────────────────────────"
cat examples/error1-connection-timeout.log
echo ""

echo "Example 2: CrashLoopBackOff"
echo "────────────────────────────────"
cat examples/error2-crashloop.log
echo ""

echo "Example 3: OOM Killed"
echo "────────────────────────────────"
cat examples/error3-oom.log
echo ""

# Step 9: Show project structure
echo "📂 Step 9: Project structure..."
tree -L 2 -I '__pycache__|*.pyc|.git|.venv|.pytest_cache|*.egg-info' . || ls -R
echo ""

# Step 10: Summary
echo "═══════════════════════════════════════════════════════════"
echo "  ✅ All checks passed!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "🎯 To use ALMOND:"
echo ""
echo "  1. Set your API key:"
echo "     export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "  2. Run diagnosis:"
echo "     almond debug --logs examples/error1-connection-timeout.log"
echo ""
echo "  3. Try different formats:"
echo "     almond debug -l error.log --format json"
echo "     almond debug -l error.log --format minimal"
echo "     almond debug -l error.log --verbose"
echo ""
echo "📖 Documentation:"
echo "   - README.md - Project overview"
echo "   - QUICKSTART.md - Complete setup guide"
echo "   - CLI_IMPLEMENTATION_SUMMARY.md - CLI details"
echo ""
echo "Happy debugging! 🌰"
