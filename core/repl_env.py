"""
core/repl_env.py — Sandboxed execution environment for the RLM engine.

Executes AI-generated Python code in a restricted scope with:
  - VAULT   : the full history.txt content (read-only string)
  - AI_FIXES: the ai_fixes.json cache (list of dicts)
  - re      : Python regex module
  - result  : output variable the code should set

Security: no builtins, no imports, no filesystem, no network.
"""

import json
import os
import re
import sys
import io
from typing import Any, Optional


class SentinelSandbox:
    """Sandboxed exec() environment for RLM code actions.

    The AI writes Python code that runs here. Only `VAULT`, `AI_FIXES`,
    `re`, and `result` are in scope — nothing else.
    """

    # Maximum output size returned to the engine (Pillar 4: Reasoning Preservation)
    MAX_OUTPUT = 2000

    def __init__(self, vault_str: str, cache_path: Optional[str] = None):
        self.vault = vault_str
        self.cache_path = cache_path
        self._ai_fixes = self._load_cache()

    def _load_cache(self) -> list:
        """Load ai_fixes.json for the AI to search programmatically."""
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def reload_cache(self) -> None:
        """Refresh the AI_FIXES variable after a new fix is committed."""
        self._ai_fixes = self._load_cache()

    def execute(self, code: str) -> str:
        """Execute AI-generated code in a restricted sandbox.

        Returns the `result` variable if set, otherwise captured stdout.
        Output is truncated intelligently to preserve the most useful
        information (first + last segments) per Pillar 4.
        """
        if not code or not code.strip():
            return "Error: No code provided."

        output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output

        # Safe builtins whitelist — blocks __import__, open, exec, eval, compile
        _SAFE_BUILTINS = {
            k: v for k, v in __builtins__.items()
            if k not in (
                "__import__", "open", "exec", "eval", "compile",
                "globals", "locals", "vars", "dir", "getattr", "setattr",
                "delattr", "breakpoint", "exit", "quit", "input",
                "memoryview", "help", "credits", "license", "copyright",
            )
        } if isinstance(__builtins__, dict) else {
            k: getattr(__builtins__, k) for k in
            ("len", "range", "enumerate", "zip", "map", "filter", "sorted",
             "reversed", "min", "max", "sum", "abs", "round", "any", "all",
             "isinstance", "issubclass", "type", "hasattr",
             "int", "float", "str", "bool", "list", "tuple", "dict", "set",
             "frozenset", "bytes", "bytearray",
             "print", "repr", "format", "chr", "ord",
             "slice", "iter", "next", "StopIteration",
             "ValueError", "TypeError", "KeyError", "IndexError",
             "RuntimeError", "Exception",
             "True", "False", "None")
            if hasattr(__builtins__, k)
        }

        # Restricted scope — safe builtins only, no filesystem, no network
        scope: dict[str, Any] = {
            "VAULT": self.vault,
            "AI_FIXES": list(self._ai_fixes),  # copy so code can't mutate cache
            "re": re,
            "result": None,
        }

        try:
            exec(code, {"__builtins__": _SAFE_BUILTINS}, scope)
        except Exception as e:
            sys.stdout = old_stdout
            return f"Error: {type(e).__name__}: {str(e)[:500]}"
        finally:
            sys.stdout = old_stdout

        # Prefer the `result` variable, fall back to stdout
        raw = scope.get("result")
        if raw is not None:
            raw_str = json.dumps(raw, default=str) if not isinstance(raw, str) else raw
        else:
            raw_str = output.getvalue()

        return self._smart_truncate(raw_str)

    def _smart_truncate(self, text: str) -> str:
        """Truncate output intelligently — keep first + last segments.

        Instead of hard-cutting at 2000 chars (losing the end where
        fixes/solutions often live), keep the first and last portions.
        """
        if len(text) <= self.MAX_OUTPUT:
            return text

        # Keep first 60% and last 40% (solutions tend to be at the end)
        head_size = int(self.MAX_OUTPUT * 0.6)
        tail_size = self.MAX_OUTPUT - head_size - 40  # room for separator

        head = text[:head_size]
        tail = text[-tail_size:]
        return f"{head}\n\n... [TRUNCATED {len(text) - self.MAX_OUTPUT} chars] ...\n\n{tail}"
