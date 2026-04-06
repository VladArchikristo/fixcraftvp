---
name: debug
description: Deep debugging session — trace errors, find root causes, suggest fixes
argument-hint: "[error message or description]"
allowed-tools: Read, Grep, Glob, Bash, Edit
---

# Debug Session

You are debugging the issue: $ARGUMENTS

Follow this systematic approach:

1. **Reproduce** — Find the error in logs, output, or by running the code
2. **Trace** — Follow the call stack from error to source
3. **Root cause** — Identify WHY it fails, not just WHERE
4. **Fix** — Apply the minimal fix that resolves the root cause
5. **Verify** — Run the code/tests to confirm the fix works

Rules:
- Check git blame if the bug was recently introduced
- Look for similar patterns elsewhere that might have the same bug
- Communicate in Russian
