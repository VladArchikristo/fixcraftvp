---
name: translate
description: Translate website content, code comments, UI text between languages. Supports bulk translation of entire projects. Russian, English, Spanish, and more.
argument-hint: "[file/folder path] [from language] [to language]"
allowed-tools: Read, Write, Edit, Glob, Grep, Agent
---

# Project Translator

Translate content across entire projects or specific files.

## Arguments

- Path, source language, target language
- Example: `/translate ~/Папка тест/fixcraftvp en ru`

## What Gets Translated

### Website Content
- All user-visible text in components (.tsx, .jsx, .vue, .html)
- Meta tags (title, description)
- Alt text on images
- Button labels, navigation items
- Error messages, form labels, placeholders

### Code
- Comments (single-line and block)
- Console messages
- README files
- Documentation

### Config
- package.json description
- manifest.json
- SEO metadata

## Process

1. Scan all files in the target path
2. Extract translatable strings
3. Translate while preserving:
   - Code syntax and structure
   - Variable names (keep in English)
   - HTML/JSX tags
   - CSS class names
   - Import statements
4. Write translations back to files OR create i18n files

## i18n Mode (optional)

If requested, instead of replacing text:
1. Extract all strings to locale files (`/locales/en.json`, `/locales/ru.json`)
2. Replace strings with translation keys: `t('hero.title')`
3. Set up next-intl or react-i18next
4. Configure language switcher component

## Output
```
=== TRANSLATION COMPLETE ===
Files processed: 12
Strings translated: 87
From: English → To: Russian
Mode: Direct replacement / i18n
```
