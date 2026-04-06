---
name: vasily-backup
description: Auto-save Vasily's trading state and memory. Trigger when: user says "сделай бэкап", "сохрани память", "запомни портфель", "backup", after any portfolio update, after opening/closing positions, after trading analysis. Vasily should use this skill proactively after every trading discussion.
---

# Vasily Auto-Backup

When this skill is triggered, save the current trading state to persistent memory.

## Steps

1. **Read current portfolio state** from the conversation context (open positions, cash, PnL)

2. **Update the session memory file** — write to:
   `/Users/vladimirprihodko/.claude/projects/-Users-vladimirprihodko------------fixcraftvp/memory/session_vasily_trading_current.md`
   
   Include:
   - Date and time
   - Open positions (asset, direction, size, entry price)
   - Cash balance
   - Total portfolio value
   - Key decisions made this session

3. **Update data/paper_portfolio.json**:
   `/Users/vladimirprihodko/Папка тест/fixcraftvp/data/paper_portfolio.json`
   
   JSON format:
   ```json
   {
     "updated": "ISO timestamp",
     "cash": 45,
     "positions": [
       {"asset": "SOL", "direction": "LONG", "size_usd": 25, "entry": 78.83},
       {"asset": "ETH", "direction": "LONG", "size_usd": 30, "entry": 2048.45}
     ],
     "notes": "brief context"
   }
   ```

4. **Confirm**: "Бэкап сделан ✓"

## Auto-trigger rules

- After opening or closing any position
- After portfolio review / PnL calculation  
- When user asks to remember anything trading-related
- At the end of any trading session
