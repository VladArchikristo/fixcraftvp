---
name: income-tracker
description: Track income and expenses across projects. Monitor progress toward the island goal (superproject).
argument-hint: "[add/show/report] [amount] [source]"
allowed-tools: Bash, Read, Write, Glob
---

# Income Tracker

Track earnings and expenses across all projects. Monitor progress toward the superproject goal.

## Data File

Store all records in `~/ObsidianVault/Income/tracker.json`. Create directory and file if they don't exist.

## JSON Structure

```json
{
  "goal": {
    "name": "Island for Science Hub",
    "target": 0,
    "currency": "USD"
  },
  "records": [
    {
      "date": "2026-03-28",
      "type": "income",
      "amount": 500,
      "source": "FixCraft client",
      "project": "fixcraft",
      "note": "Website build for client"
    }
  ]
}
```

## Arguments

### `add <amount> <source>` or `add -<amount> <expense>`
- Positive = income, negative = expense
- Auto-detect project from source keywords
- Save to tracker.json

### `show` (default if no args)
- Show recent 10 transactions
- Show current totals by project
- Show progress toward goal

### `report [month/year/all]`
- Generate financial report
- Income vs expenses breakdown
- Per-project breakdown
- Trend analysis

## Output

```
=== INCOME TRACKER ===

Total Earned:    $2,450
Total Expenses:  $320
Net Profit:      $2,130

By Project:
  FixCraft:      $1,500
  Telegram Bots: $650
  Other:         $300

Island Goal: $2,130 / $??? (set goal with /income-tracker goal <amount>)

Recent:
  2026-03-28  +$500  FixCraft client
  2026-03-25  -$20   Domain renewal
  2026-03-20  +$200  Bot subscription
```
