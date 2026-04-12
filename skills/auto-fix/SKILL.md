---
name: auto-fix
description: Automatically fix common system issues without asking the user. Trigger when: "просто исправь", "почини сам", "не спрашивай просто исправь", "auto-fix", "fix it", "сделай авто-фикс", "cosit", "косить если нужно", heartbeat detects issues like dead crons or bots.
---

# Auto-Fix

Fix issues silently. No questions. Report after.

## What to fix

### 1. Auto-save cron check
Run: `cd "/Users/vladimirprihodko/Папка тест/fixcraftvp" && git log --oneline -1`

If the last `auto-save` commit is **more than 4 hours ago**:
- Stage and commit all changes: `git add -A && git commit -m "auto-save: $(date '+%Y-%m-%d %H:%M')"`
- Push: `git push`
- Note: "Сделал коммит вручную — крон молчал X часов"

### 2. Bot health check
Check each bot via PID file:

```bash
for bot in vasily masha kostya beast; do
  pid_file="$HOME/logs/${bot}-bot.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if ! ps -p "$pid" > /dev/null 2>&1; then
      echo "DEAD: $bot (pid $pid)"
    fi
  fi
done
```

If a bot is dead — use `/bot-start` skill or run its start script directly.

Bot start scripts:
- Василий: `cd "/Users/vladimirprihodko/Папка тест/fixcraftvp/trading-bot" && nohup python3 telegram_bot.py &`
- Маша: `cd "/Users/vladimirprihodko/Папка тест/fixcraftvp/masha-bot" && nohup python3 bot.py &`
- Костя: `cd "/Users/vladimirprihodko/Папка тест/fixcraftvp/coder-bot" && nohup python3 bot.py &`

**Do NOT restart Beast** — it has a LaunchAgent, restart via: `launchctl kickstart -k gui/$(id -u)/com.vladimir.beast-bot`

### 3. Report
After fixing, reply in one short message:
- What was broken and what was fixed
- Or "все ок" if nothing needed fixing
- No bullet points for single fixes — just one casual sentence
