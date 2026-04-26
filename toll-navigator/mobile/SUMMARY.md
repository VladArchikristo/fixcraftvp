# HaulWallet Mobile App — Changes Summary

## 1. Map Routing Fix (MapScreen.js)
- **REPLACED** straight-line dashed polyline with real OSRM driving route
- Added `fetchOSRMRoute()` function that calls `https://router.project-osrm.org/route/v1/driving/...` API
- GeoJSON coordinates from OSRM are decoded and drawn as a solid blue (#4fc3f7) polyline, weight 4
- Added loading state "Building driving route..." while OSRM fetch is in progress
- **Fallback**: if OSRM fails (no network, no route found), falls back to the old straight dashed line
- Dark theme, markers, and cost badge preserved

## 2. Full English Localization
**ZERO Cyrillic characters remaining** in screens/, services/, navigation/, components/

### Files modified:
- `screens/MapScreen.js` — "Sборы" -> "Tolls", "Загрузка карты" -> "Loading map", error messages
- `screens/ResultScreen.js` — 30+ Russian strings translated (ОТКУДА/КУДА -> FROM/TO, fuel details, IFTA breakdown, tips, recommendations, etc.)
- `screens/FuelPurchaseScreen.js` — title, labels, OCR scanning text, button labels
- `screens/TripHistoryScreen.js` — ИЗ/В -> FROM/TO
- `screens/TripDetailScreen.js` — ИЗ/В -> FROM/TO
- `screens/IFTADashboardScreen.js` — comments, empty state text
- `screens/AddBrokerReviewScreen.js` — "Ваш review" -> "Your Review", alert text
- `screens/BrokerDetailScreen.js` — date locale ru-RU -> en-US, plural function fixed
- `screens/BrokerListScreen.js` — plural functions fixed (removed Russian plural 'а')
- `screens/DocumentHistoryScreen.js` — "из истории" -> "from history"
- `screens/HistoryScreen.js` — date locale ru-RU -> en-US
- `screens/ProfileScreen.js` — comment translated
- `navigation/AppNavigator.js` — All tab labels (Маршрут -> Route, Заправки -> Fuel, История -> History, Брокеры -> Brokers, Профиль -> Profile), all screen titles
- `services/brokers.js` — All comments translated
- `services/documentHistory.js` — All JSDoc comments translated
- `services/imageProcessor.js` — All comments translated

## 3. Truck Type Icons Fix (HomeScreen.js)
- 2-Axle: changed from `🚗` (car) to `🛻` (pickup truck)
- 3-Axle: kept `🚛` (delivery truck) — correct
- 5-Axle: changed from `🚜` (tractor/farm) to `🚛` (semi-truck)

## 4. Layout / Text Overflow Fixes
- **HomeScreen**: Wrapped in `SafeAreaView` for proper top spacing on notched devices
- **HomeScreen**: Truck type selector buttons use `minWidth: 0` and smaller padding to prevent horizontal overflow
- **HomeScreen**: Truck label text reduced to 11px with `textAlign: 'center'`
- **HomeScreen**: Added consistent `fontFamily` (system font) to logo
- **ResultScreen**: Grand total amount font reduced from 56px to 48px with `numberOfLines={1} adjustsFontSizeToFit`
- **ResultScreen**: Toll-only total font reduced from 52px to 44px with `numberOfLines={1} adjustsFontSizeToFit`
- **ResultScreen**: City names given `flexShrink: 1` to prevent overflow

## 5. Subscription / Premium Scaffolding
### New file: `services/subscription.js`
- `isPremium()` — checks AsyncStorage for premium flag
- `getCalcsToday()` — returns count of calculations done today
- `incrementCalcs()` — increments daily counter
- `checkLimit()` — returns `{ allowed, remaining, limit, used }`
- `upgradeToPremium()` — **MOCK** — sets premium flag in AsyncStorage
- `restorePurchases()` — **MOCK** stub
- `FREE_CALCULATIONS_LIMIT = 5` per day

### HomeScreen integration:
- Calculate button now checks daily limit before proceeding
- After 5 free calculations per day, a modal paywall appears
- Paywall shows "Upgrade to Premium" button (calls mock `upgradeToPremium()`)
- "Maybe later" dismisses the modal

### What needs real payment integration:
- Replace `upgradeToPremium()` with RevenueCat, Stripe, or App Store/Google Play IAP
- Replace `restorePurchases()` with real purchase verification
- Add server-side validation of premium status
- The AsyncStorage-based mock is for development/testing only

## 6. App Icon Review
The app icon (`assets/icon.svg`) depicts:
- A **wallet** shape (gold/amber) with a dollar sign
- A **semi-truck silhouette** (cab + trailer + 3 wheels) on top
- Highway road lines in the background
- "HaulWallet" text at the bottom

**Verdict**: The icon is appropriate — it shows a Class 8 semi-truck (cab + trailer), NOT a tractor or farm vehicle. **No redesign needed.**

## Files Modified (complete list)
1. `screens/MapScreen.js`
2. `screens/HomeScreen.js`
3. `screens/ResultScreen.js`
4. `screens/FuelPurchaseScreen.js`
5. `screens/TripHistoryScreen.js`
6. `screens/TripDetailScreen.js`
7. `screens/IFTADashboardScreen.js`
8. `screens/AddBrokerReviewScreen.js`
9. `screens/BrokerDetailScreen.js`
10. `screens/BrokerListScreen.js`
11. `screens/DocumentHistoryScreen.js`
12. `screens/HistoryScreen.js`
13. `screens/ProfileScreen.js`
14. `navigation/AppNavigator.js`
15. `services/brokers.js`
16. `services/documentHistory.js`
17. `services/imageProcessor.js`

## Files Created
1. `services/subscription.js` — subscription/premium mock service
2. `SUMMARY.md` — this file
