---
name: logo-brand
description: Generate SVG logos, color palettes, brand guidelines, and favicon sets for projects. Complete branding toolkit.
argument-hint: "[business name] [style: modern/minimal/bold/playful]"
allowed-tools: Write, Read, Bash, WebSearch, Agent
---

# Logo & Brand Generator

Create complete branding packages with SVG logos, color schemes, and brand guidelines.

## Arguments

- Business name and optional style preference
- Example: `/logo-brand FixCraft modern`

## What Gets Created

### 1. SVG Logo
- Primary logo (full)
- Icon-only version (for favicon, app icon)
- Monochrome version (for dark/light backgrounds)
- All logos as clean, scalable SVG code

### 2. Color Palette
- Primary color + shades (50-900)
- Secondary color
- Accent color
- Neutral grays
- Success/Warning/Error colors
- CSS custom properties ready to paste
- Tailwind config colors

### 3. Typography
- Recommend Google Fonts pairing (heading + body)
- Font sizes scale
- Line heights

### 4. Favicon Set
- Generate from logo SVG:
  - favicon.ico (multi-size)
  - favicon.svg
  - apple-touch-icon.png dimensions guide
  - manifest.json icons configuration

### 5. Brand Guide (markdown)
- Logo usage rules
- Color codes (HEX, RGB, HSL)
- Typography specs
- Do's and Don'ts

## Style Options

| Style | Description |
|-------|-------------|
| modern | Clean, geometric, sans-serif |
| minimal | Ultra-simple, lots of whitespace |
| bold | Strong, impactful, heavy fonts |
| playful | Rounded, colorful, friendly |
| tech | Futuristic, sharp, monospace elements |
| craft | Handmade feel, textured, warm |

## Output Files
All files saved to `<project>/public/brand/`:
- `logo.svg`, `logo-icon.svg`, `logo-mono.svg`
- `brand-guide.md`
- `colors.css`
- `favicon.svg`
