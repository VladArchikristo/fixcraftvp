---
name: quick-site
description: Quickly scaffold a new Next.js website based on FixCraft template. For client projects or new business sites.
argument-hint: "[project name] [business type, e.g. 'plumber', 'electrician', 'cleaning']"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
---

# Quick Site Generator

Scaffold a new Next.js website based on the FixCraft template for a new client or business.

## Arguments

- `$ARGUMENTS` should contain: project name and business type
- Example: `/quick-site cleanpro cleaning-service`

## Template Source

Base template: `~/Папка тест/fixcraftvp/`

## Procedure

### 1. Create Project
1. Create directory: `~/Папка тест/<project-name>/`
2. Copy template files (exclude `.next`, `node_modules`, `.env.local`, `.git`)
3. Run `npm install`

### 2. Customize
Based on business type, update:
- **page.tsx** — hero section text, business name, tagline
- **Header.tsx** — navigation links, logo text
- **Footer.tsx** — company info, contact details
- **services/** — rename and update service pages for the business type
- **globals.css** — adjust color scheme (ask user for preferred colors)
- **pricing/page.tsx** — update pricing for the business type
- **about/page.tsx** — update about text
- **contact/page.tsx** — update contact info

### 3. Verify
1. Run `npm run build` — ensure no errors
2. Run `npm run dev` — start dev server
3. Open in browser for preview

## Output

```
=== SITE CREATED ===
Project: <name>
Path: ~/Папка тест/<name>/
Type: <business type>
Dev server: http://localhost:3000

Next steps:
1. Review and customize content
2. Add real images to public/images/
3. Deploy with /deploy <name>
```

## Important
- Always ask for business name, type, and color preferences before generating
- Keep the same quality and animation level as FixCraft
- Ensure all placeholder text is replaced with relevant content
