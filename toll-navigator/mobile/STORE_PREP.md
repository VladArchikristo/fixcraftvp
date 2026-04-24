# App Store Submission Checklist — HaulWallet (Toll Navigator)

## Screenshot Requirements

Apple requires screenshots for the following display sizes. Minimum 3 screenshots per device class, up to 10.

| Device Class | Required Size | Simulator / Export |
|--------------|---------------|-------------------|
| iPhone 6.7″ (1290×2796) | **Required** | iPhone 15 Pro Max / 16 Pro Max |
| iPhone 6.5″ (1284×2778) | **Required** | iPhone 14 Pro Max / 13 Pro Max |
| iPad Pro 12.9″ (2048×2732) | **Required** | iPad Pro 12.9″ (6th gen) |

### Recommended Screens to Capture

1. **HomeScreen** — Route calculator (origin/destination inputs, vehicle type selector, map preview)
2. **ResultScreen** — Toll breakdown (total cost, per-state fees, fuel estimate, route map)
3. **HistoryScreen** — Past routes / saved trips list with search/filter
4. **DocumentScannerScreen** — Camera view scanning a fuel receipt with OCR bounding boxes
5. **FuelPurchaseForm** — Add fuel entry (gallons, price, state, odometer, IFTA quarter linkage)

### Screenshot Tips
- Use **dark mode** (app theme is dark) — ensure screenshots match `userInterfaceStyle: "dark"`
- Hide status-bar time/battery or use clean simulator bars
- Remove any debug banners / red error boxes
- Export in **PNG** or **JPEG** (high quality)

---

## Asset Checklist

| Asset | Spec | Status |
|-------|------|--------|
| App Icon | 1024×1024 px, no transparency, no alpha channel | `./assets/icon.png` |
| Splash Screen | 2732×2732 px (safe area 1200×1200), dark background `#0F172A` | `./assets/splash.png` |
| App Preview Video | Optional, 15–30 sec, no device frame | — |

---

## Metadata & URLs

| Field | Requirement | Status |
|-------|-------------|--------|
| **Privacy Policy URL** | Required; must cover location, camera, photo library usage | ☐ `https://haulwallet.com/privacy` |
| **Support URL** | Required; help desk / contact page | ☐ `https://haulwallet.com/support` |
| **Support Email** | Required for review contact / user inquiries | ☐ `support@haulwallet.com` |
| **Marketing URL** | Optional | — |

---

## Build & Signing Verification

- [ ] `bundleIdentifier` = `com.haulwallet.app`
- [ ] Version in `app.json` matches App Store Connect
- [ ] `buildNumber` incremented vs previous build
- [ ] EAS `submit.production.ios` configured with real:
  - `appleId`
  - `ascAppId`
  - `appleTeamId`
- [ ] App Store Connect record created with matching bundle ID
- [ ] No hardcoded API keys in source (verified in `config.js` — uses env vars)

---

## Permissions Review (infoPlist)

| Permission | String Present | Notes |
|------------|---------------|-------|
| Location When In Use | ✅ | `NSLocationWhenInUseUsageDescription` |
| Location Always | ✅ | `NSLocationAlwaysAndWhenInUseUsageDescription` |
| Camera | ✅ | `NSCameraUsageDescription` |
| Photo Library | ✅ | `NSPhotoLibraryUsageDescription` |
| Microphone | ⚠️ Not in iOS plist | Android has `RECORD_AUDIO` but iOS string missing. Add `NSMicrophoneUsageDescription` if video capture is used, or remove Android permission if unnecessary. |

---

## Associated Domains (Universal Links)

- **Status:** Not configured
- **Action:** If enabling universal links later, add `associatedDomains` to `ios` in `app.json`:
  ```json
  "associatedDomains": ["applinks:haulwallet.com"]
  ```
  and host the `apple-app-site-association` file on `https://haulwallet.com/.well-known/apple-app-site-association`.

---

## Privacy Manifest

- `PrivacyInfo.xcprivacy` created in project root
- Covers:
  - File timestamp / disk space APIs (document scanner)
  - UserDefaults access (AsyncStorage / auth session)
  - Precise location collection (IFTA routing)
  - Photos/Videos collection (receipt scanner)
- `NSPrivacyTracking` = false (no 3rd party analytics yet)
- `NSPrivacyTrackingDomains` empty (api.haulwallet.com is first-party)

---

## Pre-Submit Commands

```bash
cd ~/Папка\ тест/fixcraftvp/toll-navigator/mobile

# Validate project
npx expo-doctor

# Build for production
npx eas build --platform ios --profile production

# Submit to App Store (after build completes)
npx eas submit --platform ios --profile production
```

---

## Post-Launch

- [ ] Enable EAS Update channel monitoring
- [ ] Configure Sentry / Crashlytics for crash reporting (if added later)
- [ ] Add privacy policy & support links to app settings / About screen
