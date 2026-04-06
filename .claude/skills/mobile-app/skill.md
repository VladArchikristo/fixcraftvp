---
name: mobile-app
description: Scaffold and build mobile apps with React Native / Expo. Create cross-platform iOS and Android apps from scratch or convert existing web projects.
argument-hint: "[app name] [type: blank/from-web/template]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch, Agent
---

# Mobile App Builder

Create cross-platform mobile applications using React Native and Expo.

## Arguments

- `$ARGUMENTS` should contain app name and optional type
- Example: `/mobile-app fixcraft-mobile from-web`

## Modes

### blank — New App from Scratch
1. Run `npx create-expo-app <name> --template blank-typescript`
2. Set up navigation (expo-router)
3. Set up base components (Header, Screen, Button)
4. Configure theme and colors

### from-web — Convert Web Project to Mobile
1. Read existing web project structure
2. Identify reusable components and logic
3. Create Expo project with matching design
4. Adapt layouts for mobile (responsive → native)
5. Port API calls and business logic

### template — From Template
- **Business card app** — company info, services, contact
- **Chat bot app** — Telegram bot but as native app
- **Portfolio** — showcase work with gallery
- **E-commerce** — product catalog with cart

## Setup Includes
- TypeScript configuration
- Navigation (expo-router / React Navigation)
- State management (zustand or context)
- API client setup
- Splash screen and app icon configuration
- EAS Build configuration for App Store / Google Play

## Build & Test
1. `npx expo start` — start dev server
2. Test on device via Expo Go app
3. `eas build` — create production build

## Output
```
=== APP CREATED ===
Name: <app-name>
Path: ~/Папка тест/<app-name>/
Platform: iOS + Android
Dev: npx expo start
```
