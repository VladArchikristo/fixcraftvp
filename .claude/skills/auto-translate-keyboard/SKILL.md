---
name: auto-translate-keyboard
description: Auto-trigger when the user message appears to be written in English but should have been in Russian (forgot to switch keyboard layout). Detect English input from a Russian-speaking user and translate it to Russian before responding. Trigger phrases: user typed in English, wrong keyboard, forgot to switch language, message in English, translate English to Russian, перевод с английского.
---

# Auto Translate Keyboard

When a message from the user appears to be written in English (but the user is Russian-speaking and likely forgot to switch keyboard layout), automatically translate the message to Russian and treat it as if the user had typed it in Russian.

## How to detect

Translate the message if ALL of the following are true:
1. The message text is in English
2. It is NOT: a URL, a code snippet, a command (starting with `/`), a variable name, a file path, or a technical term
3. The message reads like natural conversational text or instructions (not structured data)

## What to do

1. Silently translate the English message to Russian in your head
2. Respond as if the user had typed the Russian version — do NOT comment on the language switch unless it's very obvious they made an error and a quick note would be helpful
3. Keep your response in Russian as always

## Examples

- "make the button blue" → treat as "сделай кнопку синей"
- "what is the status of the bot" → treat as "какой статус у бота"
- "fix the login bug" → treat as "почини баг с логином"
- `git status` → do NOT translate (it's a command)
- `https://example.com` → do NOT translate (it's a URL)
