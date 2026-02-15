"""
core/engine.py — The Recursive Brain (RLM Engine).

Implements all 4 RLM pillars:
  P1: Context-as-State  — VAULT + AI_FIXES as sandbox variables
  P2: Parent-Child      — ROOT_MODEL for parents, SUB_MODEL for children
  P3: Synthetic Memory  — write-back with subsume (longer patterns win)
  P4: Delta Filter      — only compressed deltas flow between recursion levels
"""

import json
import os
import re

import anthropic
from core.prompts import RLM_SYSTEM_PROMPT, RLM_CHILD_PROMPT
from core.repl_env import SentinelSandbox
from core.tools import VaultReader
from vault.ingest import Librarian


class RLMEngine:
    """The Recursive Brain — diagnoses errors by searching the Memory Vault.

    Search hierarchy:
        Tier 1: history.txt   → high-fidelity human-solved matches
        Tier 2: ai_fixes.json → previously synthesized AI fixes
        Tier 3: De novo       → LLM generates + validates from first principles
    """

    def __init__(self, api_key, vault_path, cache_path):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.root_model = os.getenv("ROOT_MODEL", "claude-3-5-haiku-20241022")
        self.sub_model = os.getenv("SUB_MODEL", "claude-3-5-haiku-20241022")
        self.max_depth = int(os.getenv("MAX_RECURSION_DEPTH", "3"))
        self.cache_path = cache_path
        self.vault_path = vault_path

        # Load the vault into the sandbox (with AI_FIXES access)
        with open(vault_path, "r", encoding="utf-8") as f:
            vault_content = f.read()
        self.sandbox = SentinelSandbox(vault_content, cache_path)

        # Reader for structured Tier 1 searches
        vault_dir = os.path.dirname(os.path.abspath(vault_path))
        self.reader = VaultReader(vault_dir)
        self.librarian = Librarian(vault_dir)

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════

    def debug(self, log_content):
        """Diagnose an error using the three-tiered search.

        Tier 1 → Tier 2 → Tier 3 (correct order per blueprint).
        Returns a dict with status + report/fix.
        """
        # ── Tier 1: Search human history (highest fidelity) ──────────
        tier1_hits = self.reader.grep(log_content[:200])
        if tier1_hits:
            context = "\n".join(
                f"[Match in entry {h.entry_id}] {h.line_content}"
                for h in tier1_hits[:5]
            )
            return self._synthesize_from_context(log_content, context)

        # ── Tier 2: Search synthetic cache ───────────────────────────
        cached = self.reader.search_cache(log_content)
        if cached:
            best = cached[0]
            self.librarian.bump_cache_hit(best["id"])
            return {
                "status": "RESOLVED_BY_CACHE",
                "fix": best,
            }

        # ── Tier 3: De novo synthesis via recursive LLM ──────────────
        trace = []  # Pillar 4: only deltas are accumulated
        report = self._recursive_search(log_content, depth=0, trace=trace)

        # Attach the reasoning trace for transparency
        if isinstance(report, dict):
            report["_trace"] = trace

        return report

    # ══════════════════════════════════════════════════════════════════
    # TIER 3: RECURSIVE SEARCH (Pillar 2 — Parent/Child)
    # ══════════════════════════════════════════════════════════════════

    def _recursive_search(self, log_content, depth, trace):
        """Tier 3: LLM writes code to search the vault, recurses on findings.

        Pillar 2: Uses ROOT_MODEL at depth 0 (parent), SUB_MODEL at depth > 0 (child).
        Pillar 4: Only deltas (not raw observations) flow into the trace.
        """
        if depth > self.max_depth:
            return {"status": "MAX_DEPTH", "msg": "Context decay imminent — stopping recursion."}

        # Parent uses root model, children use sub model
        model = self.root_model if depth == 0 else self.sub_model
        prompt = RLM_SYSTEM_PROMPT if depth == 0 else RLM_CHILD_PROMPT

        # Build the message — include accumulated deltas (not raw data)
        user_content = f"Error Log:\n{log_content}"
        if trace:
            delta_summary = "\n".join(f"  - Depth {t['depth']}: {t['delta']}" for t in trace)
            user_content += f"\n\nPrevious findings (deltas only):\n{delta_summary}"

        # Conversational loop within this depth level
        messages = [{"role": "user", "content": user_content}]

        for _step in range(5):  # max 5 code-execute steps per depth level
            response = self.client.messages.create(
                model=model,
                max_tokens=1024,
                system=prompt,
                messages=messages,
            )

            raw_text = response.content[0].text

            # Parse LLM response
            try:
                res_json = json.loads(raw_text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                res_json = self._extract_json(raw_text)
                if res_json is None:
                    return {
                        "status": "PARSE_ERROR",
                        "msg": "LLM returned non-JSON response.",
                        "raw": raw_text[:500],
                    }

            action = res_json.get("action", "")
            delta = res_json.get("delta", res_json.get("thought", ""))[:200]

            # Record delta in trace (Pillar 4: reasoning preservation)
            trace.append({"depth": depth, "action": action, "delta": delta})

            # ── EXECUTE_CODE: run in sandbox, continue loop ──────────
            if action == "EXECUTE_CODE":
                obs = self.sandbox.execute(res_json.get("code", ""))

                # Pillar 4: Compress observation into a delta for the LLM
                compressed = self._compress_observation(obs)

                # Add as assistant + user turn for conversational continuity
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({
                    "role": "user",
                    "content": f"Sandbox result:\n{compressed}\n\nContinue your analysis.",
                })
                continue

            # ── RECURSE_DEEPER: spawn child (Pillar 2) ───────────────
            if action == "RECURSE_DEEPER":
                child_context = res_json.get("context", "")[:2000]
                child_input = (
                    f"Parent's error: {log_content[:300]}\n\n"
                    f"Narrow slice to analyze:\n{child_context}"
                )
                return self._recursive_search(child_input, depth + 1, trace)

            # ── FINAL_REPORT: done ───────────────────────────────────
            if action == "FINAL_REPORT":
                report = res_json.get("report", {})

                # Pillar 3: Write back to cache + subsume
                if isinstance(report, dict) and report.get("signature"):
                    self._commit_with_subsume(
                        signature=report["signature"],
                        description=report.get("root_cause", report.get("hypothesis", "")),
                        code=report.get("solution", ""),
                    )

                return {"status": "RESOLVED_BY_SYNTHESIS", "report": report}

            # Unknown action — treat as final report
            return {"status": "UNKNOWN_ACTION", "raw": res_json}

        # Exhausted step budget at this depth
        return {"status": "STEP_LIMIT", "msg": f"Exhausted 5 steps at depth {depth}."}

    # ══════════════════════════════════════════════════════════════════
    # TIER 1: VAULT MATCH SYNTHESIS
    # ══════════════════════════════════════════════════════════════════

    def _synthesize_from_context(self, error, vault_context):
        """Use LLM to extract the solution from Tier 1 vault matches."""
        response = self.client.messages.create(
            model=self.root_model,
            max_tokens=1024,
            system=RLM_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Current Error:\n{error}\n\n"
                    f"Vault Matches (human-solved history):\n{vault_context}\n\n"
                    "These are real solutions from past incidents. "
                    "Extract the Golden Code / fix. Return a FINAL_REPORT."
                ),
            }],
        )

        raw_text = response.content[0].text
        try:
            res_json = json.loads(raw_text)
        except json.JSONDecodeError:
            res_json = self._extract_json(raw_text)
            if res_json is None:
                return {
                    "status": "RESOLVED_BY_VAULT",
                    "msg": "Found vault match but failed to parse LLM summary.",
                    "raw_context": vault_context[:1000],
                }

        report = res_json.get("report", res_json)
        return {"status": "RESOLVED_BY_VAULT", "report": report}

    # ══════════════════════════════════════════════════════════════════
    # PILLAR 3: SUBSUME LOGIC
    # ══════════════════════════════════════════════════════════════════

    def _commit_with_subsume(self, signature, description, code):
        """Write a fix to the cache, subsuming shorter (less specific) patterns.

        Subsume rule: if the new signature is LONGER (more specific) than
        an existing one that matches the same errors, replace the old one.
        """
        # Search existing cache for overlapping patterns
        existing = self.librarian.search_synthetic_cache(signature)

        for fix in existing:
            old_sig = fix.get("error_signature", "")
            if len(signature) > len(old_sig):
                # New pattern is more specific — remove the old one
                self.librarian._cache = [
                    f for f in self.librarian._cache if f["id"] != fix["id"]
                ]
                self.librarian._save_cache()

        # Commit the new fix
        self.librarian.commit_fix(
            error_signature=signature,
            fix_description=description,
            fix_code=code,
            confidence=0.6,
        )

        # Refresh sandbox's AI_FIXES variable
        self.sandbox.reload_cache()

    # ══════════════════════════════════════════════════════════════════
    # PILLAR 4: DELTA COMPRESSION
    # ══════════════════════════════════════════════════════════════════

    def _compress_observation(self, raw_output):
        """Compress sandbox output to preserve LLM reasoning quality.

        Pillar 4: The engine captures the raw dump and compresses it
        into a high-density delta. The LLM never sees noise.
        """
        if not raw_output:
            return "(empty result)"

        # If it's already short, no compression needed
        if len(raw_output) <= 800:
            return raw_output

        # For lists/JSON, keep structure but limit items
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, list) and len(parsed) > 10:
                return json.dumps(
                    {"total_matches": len(parsed), "first_5": parsed[:5], "last_3": parsed[-3:]},
                    indent=2, default=str,
                )
            return json.dumps(parsed, indent=2, default=str)[:800]
        except (json.JSONDecodeError, TypeError):
            pass

        # For raw text, keep first + last with a summary line
        lines = raw_output.split("\n")
        if len(lines) > 20:
            head = "\n".join(lines[:8])
            tail = "\n".join(lines[-5:])
            return f"{head}\n\n... [{len(lines)} total lines, showing first 8 + last 5] ...\n\n{tail}"

        return raw_output[:800]

    # ══════════════════════════════════════════════════════════════════
    # UTILS
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_json(text):
        """Try to extract a JSON object from text that may have markdown wrapping."""
        # Try to find JSON in code blocks
        match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find bare JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
