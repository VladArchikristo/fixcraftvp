# HaulWallet v13 — Build & Deploy Prompt for Claude Code

## 🎯 GOAL
Build Android AAB (versionCode 13) and upload to Google Play Console Internal Testing track.

## 📂 PROJECT PATHS
- Mobile app: `/Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/mobile`
- Backend: `/Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/backend`
- GCP service account: `/Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/gcp-service-account/service-account.json`
- Upload script: `/Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/mobile/upload_aab_only.py`

## ✅ CHANGES ALREADY MADE (do NOT modify code)
1. `screens/MapScreen.js` — added async Nominatim geocoding (full addresses supported)
2. `screens/HomeScreen.js` — truck icons: 2-axle=🛻, 3-axle=🚚, 5-axle=🚛
3. `screens/ResultScreen.js` — FIXED toll cost display (now shows real `b.cost`)
4. `backend/src/routes/tolls.js` + `geoService.js` — geocoding fallback + state extraction fix
5. `app.json` — versionCode set to 13

## 🔧 YOUR TASKS (step by step)

### Step 1: Verify Backend is Running
- Backend must be on port 3001
- Check: `curl -s http://localhost:3001/api/health`
- If not running, start it: `cd ../backend && PORT=3001 node src/server.js &`

### Step 2: Verify Code Integrity
- Run `npx eslint screens/MapScreen.js screens/HomeScreen.js screens/ResultScreen.js` (if available)
- Confirm NO syntax errors
- Confirm `app.json` has `"versionCode": 13`

### Step 3: Start EAS Build
```bash
cd /Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/mobile
npx eas build --platform android --profile production --non-interactive
```
- Wait for build to complete (takes 5-15 minutes)
- Copy the build ID and download URL from output

### Step 4: Download AAB
- Build output gives a URL like: `https://expo.dev/artifacts/...`
- Download the `.aab` file to `/tmp/haulwallet-v13.aab`

### Step 5: Upload to Google Play
```bash
python3 /Users/vladimirprihodko/Папка тест/fixcraftvp/toll-navigator/mobile/upload_aab_only.py
```
- If script asks for path, provide `/tmp/haulwallet-v13.aab`
- If upload fails, report EXACT error message

### Step 6: Report Results
Create a file `/tmp/claude_v13_report.md` with:
```markdown
# Claude v13 Build Report

## Status: [SUCCESS / PARTIAL / FAILED]

## Build Info
- Build ID: [from EAS]
- Build URL: [from EAS]
- AAB Path: [path to downloaded file]

## Upload Info
- Upload Status: [SUCCESS / FAILED]
- Version Code: 13
- Track: internal
- Google Play URL: [if available]

## Errors
[None, or list exact errors with logs]

## Verification
- [ ] Backend health check passed
- [ ] Build completed successfully
- [ ] AAB file downloaded
- [ ] Upload to Google Play succeeded
```

## ⚠️ CRITICAL RULES
1. NEVER edit `bot.py`, `.env`, `launcher.sh`, LaunchAgent plists
2. NEVER delete or modify git history
3. If ANY step fails, STOP and report the EXACT error
4. Do NOT guess — if unsure, report and wait for instructions
5. Keep terminal output — save to `/tmp/claude_v13.log`

## 🚀 SUCCESS CRITERIA
- Google Play Console shows version 13 in Internal Testing
- User can see "Update" button in Play Store on phone
