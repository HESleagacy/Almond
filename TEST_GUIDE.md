# 🧪 Complete Test Guide for ALMOND

## Quick Test Command Reference

```bash
# Run all tests (122 tests)
pytest -v

# Run with summary
pytest -v --tb=short

# Run only CLI tests (78 tests)
pytest tests/cli/ -v

# Run only Vault tests (44 tests)  
pytest tests/test_librarian.py -v

# Run specific test file
pytest tests/cli/test_display.py -v
pytest tests/cli/test_formatters.py -v
pytest tests/cli/test_main.py -v
pytest tests/cli/test_utils.py -v

# Run specific test class
pytest tests/cli/test_display.py::TestStatusDisplay -v

# Run specific test
pytest tests/cli/test_display.py::TestStatusDisplay::test_resolved_by_vault -v

# Run with coverage
pytest --cov=cli --cov=core tests/ -v

# Generate HTML coverage report
pytest --cov=cli --cov=core tests/ --cov-report=html
open htmlcov/index.html
```

## Test Breakdown

### CLI Tests (78 total)

#### Display Components (33 tests)
- `tests/cli/test_display.py`
  - StatusDisplay: 5 tests (tier colors)
  - ConfidenceIndicator: 3 tests (color coding)
  - CodeExtractor: 12 tests (language detection, rendering)
  - TraceTreeBuilder: 5 tests (tree building, truncation)
  - DebugDisplayManager: 7 tests (orchestration)

#### Formatters (17 tests)
- `tests/cli/test_formatters.py`
  - JSON format: 2 tests
  - Minimal format: 5 tests  
  - Pretty format: 5 tests
  - Router: 5 tests

#### Main CLI (17 tests)
- `tests/cli/test_main.py`
  - Debug command: 9 tests
  - Version command: 2 tests
  - Main callback: 2 tests
  - Environment validation: 2 tests

#### Utilities (11 tests)
- `tests/cli/test_utils.py`
  - File reading: 5 tests
  - Environment validation: 4 tests
  - Error handling: 5 tests

### Vault Tests (44 tests)

#### Librarian Tests
- `tests/test_librarian.py`
  - Log cleaning: 9 tests
  - Ingestion: 5 tests
  - Index integrity: 2 tests
  - Search: 6 tests
  - Edge cases: 7 tests
  - Scraping: 5 tests
  - Synthetic cache: 6 tests
  - Golden snippets: 3 tests

## Running Tests by Category

### 1. Unit Tests (Fast)
```bash
# CLI components only
pytest tests/cli/test_display.py tests/cli/test_formatters.py tests/cli/test_utils.py -v

# Takes ~0.3 seconds
```

### 2. Integration Tests
```bash
# CLI integration
pytest tests/cli/test_main.py -v

# Vault integration
pytest tests/test_librarian.py -v
```

### 3. Full Suite
```bash
# Everything
pytest -v

# Expected: 122 passed in ~0.5 seconds
```

## Test Output Examples

### Successful Run
```
============================= test session starts ==============================
platform darwin -- Python 3.11.13, pytest-9.0.2, pluggy-1.6.0
collecting ... collected 122 items

tests/cli/test_display.py::TestStatusDisplay::test_resolved_by_vault PASSED
tests/cli/test_display.py::TestStatusDisplay::test_resolved_by_cache PASSED
...
============================== 122 passed in 0.42s ==============================
```

### Failed Test
```
FAILED tests/cli/test_utils.py::TestReadLogFile::test_file_not_found - AssertionError
```

## Debugging Failed Tests

### Show Full Traceback
```bash
pytest tests/cli/test_utils.py -v --tb=long
```

### Stop at First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Verbose Output
```bash
pytest -vv
```

### Show Print Statements
```bash
pytest -s
```

## Coverage Reports

### Terminal Coverage
```bash
pytest --cov=cli --cov=core tests/ -v
```

### HTML Coverage Report
```bash
pytest --cov=cli --cov=core tests/ --cov-report=html
open htmlcov/index.html
```

### Coverage by Module
```bash
pytest --cov=cli --cov=core --cov-report=term-missing tests/ -v
```

## Continuous Testing

### Watch Mode (requires pytest-watch)
```bash
pip install pytest-watch
ptw -- -v
```

### Run on File Change
```bash
# Install entr
brew install entr  # macOS

# Watch Python files
ls **/*.py | entr pytest -v
```

## Test Examples

### Test CLI Output Formats
```bash
# Create test error
echo "ConnectionTimeout: Target unreachable" > /tmp/test.log

# Test that almond can read it (without API key, will fail at engine)
almond debug --logs /tmp/test.log 2>&1 || echo "Expected to fail without API key"
```

### Test Installation
```bash
# Verify almond command exists
which almond

# Verify Python can import
python -c "from cli.main import app; print('✅ Import successful')"

# Verify all modules
python -c "from cli import display, formatters, utils; print('✅ All CLI modules work')"
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -e .
      - run: pytest -v
```

## Troubleshooting

### Tests Not Found
```bash
# Clear pytest cache
rm -rf .pytest_cache

# Reinstall package
pip install -e .

# Run collection test
pytest --collect-only
```

### Import Errors
```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Reinstall in editable mode
pip install -e . --force-reinstall
```

### Slow Tests
```bash
# Show slowest tests
pytest --durations=10
```

## Expected Test Times

| Test Suite | Tests | Time |
|------------|-------|------|
| CLI Display | 33 | ~0.15s |
| CLI Formatters | 17 | ~0.05s |
| CLI Main | 17 | ~0.10s |
| CLI Utils | 11 | ~0.05s |
| Librarian | 44 | ~0.20s |
| **Total** | **122** | **~0.5s** |

## Success Criteria

✅ All 122 tests passing
✅ No import errors
✅ CLI commands work: `almond --help`, `almond version`
✅ Code coverage > 80%
✅ No deprecation warnings

---

**Happy Testing!** 🧪
