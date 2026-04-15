# HaulWallet — Build & Publish Instructions

## Prerequisites

1. **Node.js 18 or 20** (NOT 24 — Expo SDK 51 doesn't support it yet)
   ```bash
   nvm install 20
   nvm use 20
   ```

2. **Expo account** — register at https://expo.dev

3. **EAS CLI**
   ```bash
   npm install -g eas-cli
   ```

4. **Apple Developer account** ($99/year) — for iOS builds & TestFlight
5. **Google Play Console account** ($25 one-time) — for Android builds

---

## Step 1: Login to Expo & EAS

```bash
cd toll-navigator/mobile
npx expo login
# Enter your Expo credentials

eas login
# Same credentials
```

## Step 2: Initialize EAS project

```bash
eas init
# This will create/link the project on Expo servers
# Copy the generated projectId and paste it into app.json → extra.eas.projectId
# Also update app.json → updates.url with the same projectId
```

After `eas init`, update `app.json`:
```json
"extra": {
  "apiUrl": "https://api.haulwallet.com",
  "eas": {
    "projectId": "YOUR_ACTUAL_PROJECT_ID"
  }
},
"updates": {
  "url": "https://u.expo.dev/YOUR_ACTUAL_PROJECT_ID"
}
```

## Step 3: Configure Apple credentials (iOS)

```bash
eas credentials -p ios
# Choose: Build Credentials → Set up
# EAS will guide you through creating:
#   - Distribution certificate
#   - Provisioning profile
# You'll need your Apple ID and Team ID
```

## Step 4: Configure Google credentials (Android)

1. Go to Google Play Console → Setup → API access
2. Create a Service Account with "Release Manager" role
3. Download the JSON key file
4. Save it as `toll-navigator/mobile/google-service-account.json`
5. Add to `.gitignore`:
   ```
   google-service-account.json
   ```

## Step 5: Build for Testing

### iOS (TestFlight)
```bash
# Preview build (runs on simulator)
eas build --platform ios --profile preview

# Production build (for TestFlight)
eas build --platform ios --profile production
```

### Android (Internal Testing)
```bash
# APK for direct install
eas build --platform android --profile preview

# AAB for Google Play
eas build --platform android --profile production
```

### Both platforms at once
```bash
eas build --platform all --profile production
```

## Step 6: Submit to Stores

### iOS → TestFlight
```bash
eas submit --platform ios
# or manually:
# 1. Download .ipa from EAS dashboard
# 2. Upload via Transporter app (macOS)
# 3. Go to App Store Connect → TestFlight → manage testers
```

### Android → Google Play Internal Testing
```bash
eas submit --platform android
# or manually:
# 1. Download .aab from EAS dashboard
# 2. Go to Google Play Console → Internal testing → Create release
# 3. Upload the .aab file
# 4. Add testers by email
```

## Step 7: Update `eas.json` for auto-submit (optional)

The `eas.json` already has submit configuration. Update these placeholders:
- `appleId` — your Apple ID email
- `ascAppId` — App Store Connect app ID (found after creating app listing)
- `appleTeamId` — your Apple Developer Team ID
- `serviceAccountKeyPath` — path to Google service account JSON

---

## App Store Listing Requirements

### iOS (App Store Connect)
- Screenshots: iPhone 6.7" (1290x2796) and 6.5" (1284x2778)
- App description, keywords, categories
- Privacy policy URL (required): use https://haulwallet.com/privacy
- Age rating: 4+
- Category: Navigation / Business

### Android (Google Play Console)
- Screenshots: phone and 7" tablet
- Feature graphic: 1024x500
- Short description (80 chars): "Toll costs, IFTA reports & expense tracking for truckers"
- Full description (4000 chars)
- Privacy policy URL: https://haulwallet.com/privacy
- Content rating questionnaire
- Category: Maps & Navigation

---

## Regenerating Icons

If you need to update the app icon or splash screen:

1. Edit SVG files in `assets/icon.svg` and `assets/splash.svg`
2. Run:
   ```bash
   node scripts/generate-icons.js
   ```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EXPO_PUBLIC_API_URL` | Backend API URL | `https://api.haulwallet.com` |

The API URL is configured in three places (priority order):
1. `EXPO_PUBLIC_API_URL` env variable
2. `eas.json` → build profile → env
3. `config.js` fallback

---

## Useful Commands

```bash
# Start dev server
npx expo start

# Check project health
npx expo-doctor

# View build status
eas build:list

# OTA update (JS-only changes, no native code)
eas update --branch production --message "Fix: description"

# View logs from a device
npx expo start --dev-client
```

---

## Bundle Identifiers

- iOS: `com.haulwallet.app`
- Android: `com.haulwallet.app`

These are set in `app.json` and cannot be changed after first store submission.
