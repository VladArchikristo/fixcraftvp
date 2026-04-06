#!/bin/bash
# ClaudeClaw launcher — ensures full PATH is available for LaunchAgent.
# LaunchAgent runs with minimal env; this script sources the user profile
# so that `claude`, `bun`, and any future CLI tools are always found.

export HOME="/Users/vladimirprihodko"

# Source profile to get the real PATH (same as terminal)
if [ -f "$HOME/.zprofile" ]; then
  source "$HOME/.zprofile"
fi
if [ -f "$HOME/.zshrc" ]; then
  # zshrc may use zsh-only syntax, so just extract PATH exports
  eval "$(grep 'export PATH' "$HOME/.zshrc" 2>/dev/null)"
fi

# Fallback: guarantee critical paths are present
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$HOME/Library/Python/3.9/bin:$PATH"

export BUN_INSTALL="$HOME/.bun"

cd "/Users/vladimirprihodko/Папка тест/fixcraftvp" || exit 1

exec "$HOME/.bun/bin/bun" run \
  "$HOME/.claude/plugins/cache/claudeclaw/claudeclaw/1.0.0/src/index.ts" \
  start --web
