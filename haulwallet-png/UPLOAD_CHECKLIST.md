# HaulWallet — Play Store Upload Checklist

> Generated: 2026-04-17
> All files are in `/haulwallet-png/`

---

## CRITICAL ISSUE: All PNGs are 2048x2048

Every PNG file has identical dimensions of **2048x2048 px** — this is because the SVG source files were rasterized at a fixed canvas size, not at their intended display dimensions. **These files cannot be uploaded to Play Store as-is.** They must be re-exported at correct dimensions.

---

## 1. App Icon

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `app-icon-512.svg.png` | 2048x2048 | 512x512 PNG | ❌ Wrong size — re-export at 512x512 |
| `app-icon-1024.svg.png` | 2048x2048 | 512x512 PNG (max 1024x1024) | ❌ Wrong size — re-export at 512x512 |

**Play Store requirement:** Exactly 512x512 px, PNG, no transparency (alpha).

---

## 2. Feature Graphic

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `feature-graphic-1024x500.svg.png` | 2048x2048 | 1024x500 PNG | ❌ Wrong size — re-export at 1024x500 |

**Play Store requirement:** Exactly 1024x500 px, PNG or JPG.

---

## 3. Phone Screenshots

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `phone-screen-1-dashboard.svg.png` | 2048x2048 | Shortest side 320–3840px, aspect 9:16 or 16:9 | ❌ Square (1:1) — wrong aspect ratio |
| `phone-screen-2-loads.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `phone-screen-3-map.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `phone-screen-4-earnings.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-phone-1-dashboard.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-phone-2-map.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-phone-3-loads.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-phone-4-earnings.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-phone-5-login.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |

**Play Store requirement:** PNG or JPG, shortest side 320–3840px, aspect ratio 16:9 or 9:16. Recommended: 1080x1920 (portrait) or 1920x1080 (landscape).

---

## 4. 7-inch Tablet Screenshots

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `tablet-7inch-screen-1.svg.png` | 2048x2048 | Shortest side 320–3840px, 16:9 or 9:16 | ❌ Square (1:1) |
| `tablet-7inch-screen-2.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-tablet7-1-dashboard.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-tablet7-2-loads.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |

**Play Store requirement:** Same as phone screenshots. Recommended: 1200x1920 (portrait).

---

## 5. 10-inch Tablet Screenshots

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `tablet-10inch-screen-1.svg.png` | 2048x2048 | Shortest side 320–3840px, 16:9 or 9:16 | ❌ Square (1:1) |
| `tablet-10inch-screen-2.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-tablet10-1-overview.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-tablet10-2-analytics.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |

**Play Store requirement:** Same as phone screenshots. Recommended: 1600x2560 (portrait).

---

## 6. Chromebook Screenshots

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `chromebook-screen-1.svg.png` | 2048x2048 | Min 1 screenshot, 16:9 aspect ratio | ❌ Square (1:1) |
| `chromebook-screen-2.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-chromebook-1-main.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-chromebook-2-analytics.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |
| `screenshot-chromebook-3-loads.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |

**Play Store requirement:** PNG or JPG, 16:9 landscape, minimum 1920x1080. At least 1 required.

---

## 7. XR (Android XR / Spatial)

| File | Actual Size | Required | Status |
|------|------------|----------|--------|
| `xr-screen-1.svg.png` | 2048x2048 | 16:9 landscape | ❌ Square (1:1) |
| `xr-screen-2.svg.png` | 2048x2048 | Same | ❌ Square (1:1) |

**Play Store requirement:** 16:9 landscape screenshots for XR devices.

---

## 8. Extras (not required for Play Store)

| File | Notes |
|------|-------|
| `youtube-thumbnail-concept.svg.png` | Not needed for Play Store |
| `youtube-thumbnail.svg.png` | Not needed for Play Store |

---

## Summary

| Category | Files | Status |
|----------|-------|--------|
| App Icon | 2 | ❌ All wrong size |
| Feature Graphic | 1 | ❌ Wrong size |
| Phone Screenshots | 9 | ❌ All wrong aspect ratio |
| 7" Tablet | 4 | ❌ All wrong aspect ratio |
| 10" Tablet | 4 | ❌ All wrong aspect ratio |
| Chromebook | 5 | ❌ All wrong aspect ratio |
| XR | 2 | ❌ All wrong aspect ratio |

**Ready for upload: 0 / 27 files**

---

## Fix: How to Re-export Correctly

The SVG source files exist in `/haulwallet-assets/`. Use one of these methods:

### Option A — Inkscape CLI (batch)
```bash
# App icon 512x512
inkscape --export-type=png --export-width=512 --export-height=512 \
  --export-filename=app-icon-512.png haulwallet-assets/app-icon-512.svg

# Feature graphic 1024x500
inkscape --export-type=png --export-width=1024 --export-height=500 \
  --export-filename=feature-graphic.png haulwallet-assets/feature-graphic-1024x500.svg

# Phone screenshots 1080x1920
inkscape --export-type=png --export-width=1080 --export-height=1920 \
  --export-filename=phone-screen-1.png haulwallet-assets/phone-screen-1-dashboard.svg
```

### Option B — rsvg-convert
```bash
# brew install librsvg
rsvg-convert -w 512 -h 512 haulwallet-assets/app-icon-512.svg -o app-icon-512.png
rsvg-convert -w 1024 -h 500 haulwallet-assets/feature-graphic-1024x500.svg -o feature-graphic.png
rsvg-convert -w 1080 -h 1920 haulwallet-assets/phone-screen-1-dashboard.svg -o phone-1.png
```

### Recommended target dimensions
| Asset | Width | Height |
|-------|-------|--------|
| App icon | 512 | 512 |
| Feature graphic | 1024 | 500 |
| Phone portrait | 1080 | 1920 |
| 7" tablet portrait | 1200 | 1920 |
| 10" tablet portrait | 1600 | 2560 |
| Chromebook landscape | 1920 | 1080 |
| XR landscape | 1920 | 1080 |

---

> Note: Duplicate sets exist (e.g. `phone-screen-*` and `screenshot-phone-*`). Choose one set per category before uploading.
