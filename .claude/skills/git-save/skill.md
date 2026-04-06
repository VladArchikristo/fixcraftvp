---
name: git-save
description: Quick git commit and push with auto-generated commit message. Saves all changes in current project.
argument-hint: "[commit message or leave empty for auto-message]"
allowed-tools: Bash, Read, Grep, Glob
---

# Git Quick Save

Fast commit and push all changes with smart auto-generated commit message.

## Procedure

### 1. Check State
- Run `git status` to see changes
- If no changes — report "Nothing to save" and exit
- If not a git repo — offer to initialize one with `git init`

### 2. Stage Changes
- Stage all modified and new files: `git add -A`
- Exclude sensitive files: check for `.env`, credentials, API keys — warn user if found

### 3. Generate Commit Message
If `$ARGUMENTS` is provided, use it as commit message.
If empty, auto-generate based on:
- Analyze `git diff --cached --stat` for changed files
- Determine type: feat/fix/refactor/docs/style/chore
- Create concise message in format: `type: brief description`

### 4. Commit
```
git commit -m "<message>"
```

### 5. Push
- Check if remote exists: `git remote -v`
- If remote exists: `git push`
- If no remote: ask user if they want to add one
- If no upstream branch: `git push -u origin <branch>`

## Output

```
=== SAVED ===
Branch: main
Commit: abc1234 — feat: add contact form validation
Files changed: 3 (+45 -12)
Pushed to: origin/main
```

## Safety
- ALWAYS warn about `.env` files or anything with API keys/tokens before committing
- Never force push
- Never push to main/master without confirmation
