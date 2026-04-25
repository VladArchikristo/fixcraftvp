# Toll Navigator — Store Assets Status

## ✅ Ready Now

### iOS (App Store)
- [x] `app.json` configured: `bundleIdentifier: com.haulwallet.app`, `buildNumber: 1`
- [x] InfoPlist strings: location (when-in-use + always), camera, photo library — all localized
- [x] Background modes: location, fetch
- [x] `PrivacyInfo.xcprivacy` — created and present in mobile directory
- [x] Dark mode enforced (`userInterfaceStyle: dark`)
- [x] Expo SDK 51, runtimeVersion policy: appVersion
- [x] EAS updates URL configured

### Android (Google Play)
- [x] `app.json` configured: `package: com.haulwallet.app`, `versionCode: 1`
- [x] Adaptive icon with background color `#0F172A`
- [x] Permissions: camera, storage, location (fine/coarse/background), foreground service, record audio
- [x] `eas.json` production profile: autoIncrement enabled

### EAS Build
- [x] `eas.json` development/preview/production profiles set
- [x] Environment variable `EXPO_PUBLIC_API_URL` points to `https://api.haulwallet.com`
- [x] EAS Project ID: `ff7f070e-42d7-439b-9dc9-68ad352c23b0`

## ⚠️ Needs Action (No Money Required)
- [ ] **Screenshots** — need 5–10 device frames:
  - iPhone 6.7" (1290×2796)
  - iPhone 6.5" (1284×2778)
  - iPad Pro 12.9" (2048×2732)
  - Android phone (1080×1920)
  - Android tablet (optional)
  - *Action:* Build preview with `eas build --profile preview`, install on simulator, capture screens
- [ ] **Feature graphic** for Google Play (1024×500)
- [ ] **App icon** — verify `./assets/icon.png` is 1024×1024
- [ ] **Splash screen** — verify `./assets/splash.png` is 1242×2438

## ❌ Blocked (Requires Money / Accounts)
- [ ] **Apple Developer Account** ($99/year)
  - Needed for: App Store submission, TestFlight, EAS production build signing
  - `eas.json` has placeholders: `appleId`, `ascAppId`, `appleTeamId`
- [ ] **Google Play Console** ($25 one-time)
  - Needed for: Play Store submission
  - `eas.json` needs: `serviceAccountKeyPath` (JSON key from Google Cloud)
- [ ] **Apple Team ID**
  - Replace `YOUR_TEAM_ID` in `eas.json`

## 📝 Store Listing Draft (English)

**App Name:** HaulWallet — Toll Calculator for Truckers

**Subtitle:** Calculate tolls, fuel & IFTA for any US route

**Description:**
HaulWallet helps truck drivers and fleet owners calculate exact toll costs, fuel expenses, and IFTA quarterly tax reports for any route across the United States.

• Toll calculation for 3,700+ toll roads in 47 states
• Real-time route planning with state-by-state mileage
• IFTA fuel tax reporting (Q1–Q4)
• Fuel receipt OCR scanning
• Broker check & reviews (MC/DOT lookup)
• Live load tracking for brokers
• Background GPS mileage logging

Built by truckers, for truckers.

**Keywords:** truck toll calculator, IFTA, trucking expenses, fuel receipt scanner, route planner, toll road, fleet management, owner-operator, DOT broker check

**Category:** Navigation / Utilities

**Support URL:** https://haulwallet.com
**Privacy Policy URL:** https://haulwallet.com/privacy

## 🎯 Next Steps
1. Buy Apple Developer account ($99) + Google Play Console ($25)
2. Set Team ID in `eas.json`
3. Generate Google Service Account JSON
4. Build screenshots via preview/simulator
5. Run `eas build --platform all --profile production`
6. Submit to App Store + Play Store
