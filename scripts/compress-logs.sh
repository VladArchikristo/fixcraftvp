#!/bin/bash
# Weekly conversation log compressor
# - Summarizes old logs (>7 days) via Haiku into digest
# - Gzips raw logs
# - Syncs digest to Obsidian vault

set -euo pipefail

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PROJECT_DIR="$HOME/Папка тест/fixcraftvp"
OBSIDIAN_DIR="$HOME/ObsidianVault/ClaudeClaw-Memory/conversation-digests"

# Читаем токены из .env
ENV_FILE="$PROJECT_DIR/trading-bot/.env"
if [ -f "$ENV_FILE" ]; then
    TELEGRAM_TOKEN=$(grep '^COMPRESS_BOT_TOKEN=' "$ENV_FILE" | cut -d'=' -f2-)
    CHAT_ID=$(grep '^VASILY_CHAT_ID=' "$ENV_FILE" | cut -d'=' -f2-)
fi
TELEGRAM_TOKEN="${TELEGRAM_TOKEN:-}"
CHAT_ID="${CHAT_ID:-244710532}"
LOG_FILE="$HOME/logs/cron/compress-logs.log"
WEEK=$(date '+%Y-W%V')
CUTOFF_DATE=$(date -v-7d '+%Y-%m-%dT00:00:00')

mkdir -p "$OBSIDIAN_DIR" "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

send_telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$1" \
        -d parse_mode="Markdown" > /dev/null 2>&1
}

process_bot() {
    local bot_name="$1"
    local bot_dir="$2"
    local logfile="$bot_dir/conversation_log.jsonl"

    if [ ! -f "$logfile" ]; then
        log "$bot_name: no conversation_log.jsonl found, skipping"
        return 0
    fi

    local total_lines=$(wc -l < "$logfile" | tr -d ' ')
    if [ "$total_lines" -eq 0 ]; then
        log "$bot_name: empty log, skipping"
        return 0
    fi

    # Split: old lines (before cutoff) and recent lines (keep)
    local old_file=$(mktemp)
    local new_file=$(mktemp)

    # Filter by timestamp using python for reliability
    python3 -c "
import json, sys
cutoff = '$CUTOFF_DATE'
old = open('$old_file', 'w')
new = open('$new_file', 'w')
for line in open('$logfile'):
    line = line.strip()
    if not line:
        continue
    try:
        entry = json.loads(line)
        ts = entry.get('ts', '')
        if ts < cutoff:
            old.write(line + '\n')
        else:
            new.write(line + '\n')
    except:
        new.write(line + '\n')
old.close()
new.close()
"

    local old_count=$(wc -l < "$old_file" | tr -d ' ')

    if [ "$old_count" -eq 0 ]; then
        log "$bot_name: no old messages to compress"
        rm -f "$old_file" "$new_file"
        return 0
    fi

    log "$bot_name: compressing $old_count old messages"

    # Summarize via Haiku (limit input to avoid token overflow)
    local old_content=$(head -c 50000 "$old_file")
    local digest=""
    digest=$("$HOME/.local/bin/claude" -p "Вот лог разговоров бота $bot_name за неделю. Сделай краткий дайджест на русском:
- Основные темы разговоров
- Ключевые запросы пользователя
- Важные решения и ответы
- Проблемы если были

Лог:
$old_content" --model claude-haiku-4-5-20251001 --output-format text 2>/dev/null) || {
        log "$bot_name: Haiku summarization failed, keeping raw logs"
        rm -f "$old_file" "$new_file"
        return 1
    }

    # Save digest
    local digest_file="$bot_dir/conversation_digest.md"
    {
        echo ""
        echo "## $bot_name — $WEEK"
        echo ""
        echo "$digest"
        echo ""
        echo "---"
    } >> "$digest_file"

    # Copy digest to Obsidian
    cp "$digest_file" "$OBSIDIAN_DIR/${bot_name}-digest.md"

    # Gzip old raw logs
    local archive="$bot_dir/conversation_log_${WEEK}.jsonl.gz"
    gzip -c "$old_file" > "$archive"
    log "$bot_name: archived to $archive"

    # Replace current log with only recent messages
    mv "$new_file" "$logfile"

    rm -f "$old_file"
    log "$bot_name: done — $old_count messages compressed, digest saved"
    echo "$bot_name: $old_count msgs"
}

# Process all bots
log "=== Weekly log compression started ==="

results=""
for bot in "Маша:$PROJECT_DIR/masha-bot" "Вася:$PROJECT_DIR/trading-bot" "Beast:$PROJECT_DIR/beast-bot"; do
    name="${bot%%:*}"
    dir="${bot##*:}"
    result=$(process_bot "$name" "$dir" 2>&1) || true
    if [ -n "$result" ]; then
        results+="$result\n"
    fi
done

log "=== Compression complete ==="

if [ -n "$results" ]; then
    send_telegram "📦 *Сжатие логов ($WEEK)*
$results
Дайджесты в Obsidian ✅"
else
    send_telegram "📦 *Сжатие логов ($WEEK)*
Нет старых записей для сжатия"
fi
