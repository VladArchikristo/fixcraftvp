---
name: bot-start
description: Start, stop, or check status of Telegram bots. Manages all bot instances.
argument-hint: "[bot name: claude/gemini/all] [action: start/stop/status]"
allowed-tools: Bash, Read, Grep, Glob
---

# Telegram Bot Manager

Manage all Telegram bots — start, stop, check status.

## Known Bots

| Name | Path | Type |
|------|------|------|
| claude | `~/my_bot/bot.py` | Claude API |
| gemini | `~/my_gemini_bot/bot.py` | Google Gemini |
| claude-cli | `~/claude_telegram_bot.py` | Claude CLI |

## Arguments

Parse `$ARGUMENTS` for:
- **Bot name**: `claude`, `gemini`, `claude-cli`, or `all`
- **Action**: `start`, `stop`, `status` (default: `status`)

If no arguments — show status of all bots.

## Actions

### status
1. Check if bot process is running: `ps aux | grep bot.py`
2. Show PID, uptime, memory usage
3. Show last log lines if available

### start
1. Check if bot is already running — warn if so
2. Verify `.env` file exists with required tokens
3. Start bot in background: `nohup python3 <path> > ~/logs/<bot-name>.log 2>&1 &`
4. Create `~/logs/` directory if needed
5. Wait 3 seconds, verify process is alive
6. Show PID and log tail

### stop
1. Find bot PID: `pgrep -f <bot-path>`
2. Send SIGTERM gracefully
3. Wait 3 seconds, verify stopped
4. If still running, send SIGKILL

## Output

```
=== BOT STATUS ===
claude:     Running (PID 12345, uptime 2h 30m)
gemini:     Stopped
claude-cli: Stopped
```

## Safety
- Always check if a bot is already running before starting a new instance
- Never start multiple instances of the same bot
- Always use graceful shutdown first
