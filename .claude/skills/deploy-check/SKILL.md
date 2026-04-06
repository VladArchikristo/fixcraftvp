---
name: deploy-check
description: Pre-deployment checklist — verify the project is ready for deployment
allowed-tools: Read, Grep, Glob, Bash
---

# Pre-Deploy Check

Run through this deployment readiness checklist:

1. **Dependencies** — Check for outdated or vulnerable packages
2. **Tests** — Run full test suite, report failures
3. **Lint** — Run linter, check for warnings/errors
4. **Build** — Verify production build succeeds
5. **Env vars** — Check all required environment variables are set
6. **Secrets** — Scan for hardcoded secrets or credentials in code
7. **Config** — Verify production config is correct
8. **Git** — Check for uncommitted changes, verify branch is clean

Output a summary table with status (pass/fail/warning) for each item.
Communicate in Russian.
