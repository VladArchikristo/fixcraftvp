---
name: cleanup
description: Auto-cleanup context when it gets bloated. Compacts conversation, saves important state to memory, removes noise. Use proactively when context exceeds 60%.
user-invocable: true
---

# Context Cleanup

Perform an intelligent context cleanup to prevent glitches and slowdowns:

1. **Save important state to memory** — if there is any unsaved progress, decisions, or context that would be lost, write it to memory files in `~/.claude/projects/` memory directory BEFORE compacting.

2. **Run /compact** with a focused summary of:
   - Current active task and its progress
   - Key decisions already made
   - File paths that were modified
   - Next steps to continue work

3. After compacting, confirm to the user (in Russian):
   - What was saved to memory
   - Current context usage
   - Ready to continue
