---
name: monitor
description: Check if websites, APIs, and bots are online and responding. Health check for all services.
argument-hint: "[url or service name, e.g. 'fixcraft' or 'bots']"
allowed-tools: Bash, Read, Grep, WebFetch
---

# Service Monitor

Check health and availability of websites, APIs, and bots.

## Target

If `$ARGUMENTS` is provided, check that specific service/URL.
If empty, check ALL known services.

## Known Services

### Websites
- FixCraft — check if deployed (look for Vercel/Netlify URL in deploy history or .vercel directory)

### Bots
- Claude bot (`~/my_bot/bot.py`) — check process running
- Gemini bot (`~/my_gemini_bot/bot.py`) — check process running

### System
- VPN status — check `utun` interfaces
- Internet connectivity — ping test
- DNS resolution — test

## Check Procedure

### For URLs
1. `curl -s -o /dev/null -w "%{http_code} %{time_total}s" <url>`
2. Report HTTP status code and response time
3. FLAG: status != 200, response time > 5s

### For Bots
1. `pgrep -f <bot-file>` — check if process exists
2. Check last modification of log file
3. Check for error patterns in recent logs

### For System
1. Internet: `curl -s -o /dev/null -w "%{http_code}" https://1.1.1.1`
2. DNS: `nslookup google.com`
3. VPN: `ifconfig | grep utun`
4. Disk space: `df -h /`

## Output

```
=== HEALTH CHECK ===

Network
  Internet:  Online (15ms)
  DNS:       Working
  VPN:       Active (utun6)

Bots
  claude:    Running (PID 12345)
  gemini:    Stopped

System
  Disk:      72% used (45GB free)
  Memory:    4.2GB available

Websites
  fixcraft:  200 OK (0.45s)
```
