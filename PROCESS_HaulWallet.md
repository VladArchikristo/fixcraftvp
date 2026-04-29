# 🚛 HaulWallet — Process "Work Without Hermes"

## 🎯 Concept
You (Vlad) run Claude Code with a prepared prompt. Claude does the coding. You verify. Hermes only checks + deploys.

## 📀 Files You Need
| File | Purpose |
|------|---------|
| `CLAUDE_PROMPT_v{VERSION}.md` | Exact instructions for Claude Code |
| `CHECKLIST_AFTER_CLAUDE.md` | What to verify after Claude finishes |
| `DEPLOY_GUIDE.md` | How to upload to Google Play Console |

## 🧵 Full Workflow

```
YOU: Write what needs to be changed (ex: "add geocoding for addresses")
  ↓
Hermes OR You: Create CLAUDE_PROMPT_v{VERSION}.md (fill template below)
  ↓
YOU: Run in terminal: cd mobile && claude -p "$(cat CLAUDE_PROMPT_v13.md)"
  ↓
Claude Code: Builds, fixes, uploads AAB to Expo
  ↓
YOU: Open CHECKLIST_AFTER_CLAUDE.md, run each command, verify outputs
  ↓
If all checks pass → Open DEPLOY_GUIDE.md, upload to Google Play
  ↓
If checks FAIL → Copy errors, send to Hermes, wait for fix
```

## 📝 Step 1: Write Claude Prompt (Template)

```markdown
# HaulWallet v{VERSION} — Build & Deploy Prompt for Claude Code

## GOAL
[One sentence: what to build]

## CHANGES REQUIRED
1. File X — do Y
2. File Z — do W

## STEPS FOR CLAUDE
1. Run `npx eslint screens/*.js` — confirm no errors
2. Run `npx eas build --platform android --profile production`
3. Report build ID and status

## CRITICAL RULES
- NEVER edit .env, bot.py, launcher.sh
- If ANY step fails, STOP and report exact error
- Save terminal output to /tmp/claude_v{VERSION}.log
```

## ✅ Step 2: Verification Checklist (After Claude Finishes)

Run these commands IN ORDER:

```bash
# 1. Check syntax
npx eslint screens/*.js services/*.js
# Expected: clean output, no errors

# 2. Check versionCode
 cat app.json | grep versionCode
# Expected: number incremented

# 3. Check backend health
curl -s http://localhost:3001/api/health
# Expected: {"status":"ok"}

# 4. Check build log
tail -30 /tmp/claude_v{VERSION}.log
# Expected: "Build finished" or "Upload succeeded"

# 5. If AAB downloaded, check size
ls -lh /tmp/haulwallet-*.aab
# Expected: file exists, ~50-100 MB
```

**If ALL checks pass** → Proceed to deploy.

**If ANY check fails** → STOP. Send `/tmp/claude_v{VERSION}.log` to Hermes.

## 🚀 Step 3: Deploy Guide

See `DEPLOY_GUIDE.md` for exact clicks in Google Play Console.

## 👨‍🔧 When Do You Still Need Hermes?
- Backend crashes or logic bugs
- Database migrations
- New API integrations (Nominatim, payment systems)
- Complex multi-file refactors
- "I don't understand why this fails"

---
Created by Hermes. Update this when process changes.
