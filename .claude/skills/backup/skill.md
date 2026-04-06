---
name: backup
description: Backup all projects and Claude memory to a timestamped archive. Use to create backups before major changes or on demand.
argument-hint: "[project name or leave empty for full backup]"
allowed-tools: Bash, Glob, Read
---

# Full Backup Tool

Create timestamped backups of all projects and Claude memory.

## Backup Location

All backups go to `~/Backups/`. Create the directory if it doesn't exist.

## Target

If `$ARGUMENTS` is provided, backup only that specific project.
If `$ARGUMENTS` is empty, backup EVERYTHING listed below.

## What to Backup

### 1. Claude Memory
- Source: `~/.claude/projects/-Users-vladimirprikhodko/memory/`
- Also: `~/.claude/skills/` (all custom skills)

### 2. Projects
- FixCraft: `~/Папка тест/fixcraftvp/` (exclude `node_modules`, `.next`)
- Telegram bots: `~/my_bot/`, `~/my_gemini_bot/`, `~/claude_telegram_bot.py`, `~/Documents/files телеграмм бот/`
- Obsidian Vault: `~/ObsidianVault/`

### 3. Config Files
- `~/.zshrc`
- `~/.claude/` config files (settings.json, CLAUDE.md)
- VSCode settings: `~/Library/Application Support/Code/User/settings.json`
- VSCode keybindings: `~/Library/Application Support/Code/User/keybindings.json`
- LaunchAgents: `~/Library/LaunchAgents/com.vladimir.*`

## Procedure

1. Create backup directory: `~/Backups/backup-YYYY-MM-DD-HHMMSS/`
2. Copy all sources (excluding node_modules, .next, .git, __pycache__)
3. Create a compressed archive: `tar -czf ~/Backups/backup-YYYY-MM-DD-HHMMSS.tar.gz`
4. Remove the uncompressed directory
5. Show backup size and contents summary
6. Clean up old backups — keep only the last 5

## Output

```
=== BACKUP COMPLETE ===
Date: YYYY-MM-DD HH:MM:SS
Archive: ~/Backups/backup-YYYY-MM-DD-HHMMSS.tar.gz
Size: X MB
Contents: N files from M projects
```
