# Demo Scenarios: The Bugs

Show this file to the judges to explain what ALMOND is solving.

## 1. The "Protocol Mismatch" (Tier 1)
**File**: `examples/tier1-legacy-memory.log`
**The Bug**:
> `Connection failed: V1 handshake rejected by server (Requires V2)`
- **Context**: An old legacy system trying to talk to a modern API.
- **Why it's hard**: The error message is generic "Connection failed".
- **Why ALMOND solves it**: It remembers the exact config change `FORCE_V1_HANDSHAKE` from 2025 (in `vault/history.txt`).

## 2. The "Async Deadlock" (Tier 3)
**File**: `examples/tier3-novel-bug.log`
**The Bug**:
> `FATAL: Deadlock in Async Worker - Mutex acquisition timeout`
- **Context**: A brand new feature (Async Workers) released today.
- **Why it's hard**: It's a "Deadlock". There is no stack trace pointing to a specific line, just a timeout.
- **Why ALMOND solves it**: It reads the logs, hypothesizes a "Mutex Livelock", and writes new code to fix the synchronization logic.

---

**Tip**: Open the `.log` files directly to show they are "raw" server logs.
