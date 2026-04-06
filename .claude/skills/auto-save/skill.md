---
name: auto-save
description: Auto-save all memory, progress, and context to Obsidian vault and backup. Run manually or on schedule to never lose context.
argument-hint: "[full/quick]"
allowed-tools: Bash, Read, Write, Glob
---

# Auto-Save to Obsidian & Backup

Save all current memory, context, and progress to Obsidian vault.

## Mode

If `$ARGUMENTS` is `full` — full backup (archive + Obsidian sync).
If `$ARGUMENTS` is `quick` or empty — quick sync (memory to Obsidian only).

## Quick Sync

1. Copy all Claude memory files to Obsidian:
   ```bash
   cp -f ~/.claude/projects/-Users-vladimirprikhodko/memory/*.md ~/ObsidianVault/Claude-Memory/
   ```

2. Copy ClaudeClaw memory if exists:
   ```bash
   cp -f ~/Папка\ тест/fixcraftvp/.claude/claudeclaw/logs/daemon.log ~/ObsidianVault/ClaudeClaw-Memory/daemon-latest.log 2>/dev/null
   ```

3. Create a sync timestamp:
   ```bash
   echo "Last sync: $(date '+%Y-%m-%d %H:%M:%S')" > ~/ObsidianVault/last-sync.md
   ```

## Full Backup

1. Do everything from Quick Sync
2. Create timestamped archive:
   ```bash
   tar -czf ~/Backups/backup-$(date +%Y-%m-%d-%H%M%S).tar.gz \
     -C ~ .claude/projects/-Users-vladimirprikhodko/memory/ \
     -C ~ .claude/skills/ \
     -C ~ ObsidianVault/ \
     --exclude='.obsidian/workspace*'
   ```
3. Keep only last 5 backups — delete older ones

## Output

```
=== AUTO-SAVE COMPLETE ===
Mode: quick/full
Time: YYYY-MM-DD HH:MM:SS
Claude Memory: N files synced
ClaudeClaw Memory: synced/not found
Backup: created (full only)
```
