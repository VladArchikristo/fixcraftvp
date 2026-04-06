---
name: deploy
description: Deploy a project to Vercel or Netlify. Handles build checks, environment variables, and deployment.
argument-hint: "[project path or name, e.g. 'fixcraft']"
allowed-tools: Bash, Read, Glob, Grep, WebSearch
---

# Project Deployer

Deploy web projects to Vercel or Netlify.

## Target

If `$ARGUMENTS` is provided, use it as project name or path.
If empty, look for a project in the current directory.

## Known Projects
- `fixcraft` → `~/Папка тест/fixcraftvp/`

## Pre-Deploy Checks

1. **Build test** — run `npm run build` and ensure it passes
2. **Environment variables** — check `.env.local` / `.env` for required vars
3. **Package.json** — verify scripts exist (build, start)
4. **Dependencies** — ensure `node_modules` exists, run `npm install` if needed

## Deploy Procedure

### Vercel (preferred for Next.js)
1. Check if `vercel` CLI is installed, install if not: `npm i -g vercel`
2. Run `vercel --prod` from project directory
3. Report the deployment URL

### Netlify (fallback)
1. Check if `netlify-cli` is installed
2. Run `netlify deploy --prod --dir=.next`
3. Report the deployment URL

## Output

```
=== DEPLOY COMPLETE ===
Project: project-name
Platform: Vercel/Netlify
URL: https://...
Status: Live
```

## Error Handling
- If build fails — show errors and suggest fixes
- If CLI not installed — install it automatically
- If not logged in — guide user through auth
