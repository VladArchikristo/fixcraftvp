#!/bin/bash
# Daily Bot Health Check — отправляет статус всех ботов в Telegram

TOKEN="${BOT_STATUS_TOKEN:-}"
CHAT_ID="244710532"
LOG_DIR="$HOME/logs"

if [ -z "$TOKEN" ]; then
    echo "Error: BOT_STATUS_TOKEN not set"
    exit 1
fi

MESSAGE="📊 <b>Daily Bot Status</b> — $(date '+%Y-%m-%d %H:%M')\n\n"

for bot in beast kostya masha vasily philip peter zina alexey; do
    PID_FILE="$LOG_DIR/${bot}-bot.pid"
    HEARTBEAT="$LOG_DIR/${bot}-heartbeat"

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            UPTIME=$(ps -p "$PID" -o etime= | tr -d ' ')
            STATUS="✅ UP (${UPTIME})"
        else
            STATUS="❌ DEAD (PID $PID not found)"
        fi
    else
        STATUS="⚠️ NO PID FILE"
    fi

    # Check heartbeat freshness (within 5 min)
    if [ -f "$HEARTBEAT" ]; then
        HB_AGE=$(( $(date +%s) - $(stat -f%m "$HEARTBEAT" 2>/dev/null || stat -c%Y "$HEARTBEAT") ))
        if [ "$HB_AGE" -gt 300 ]; then
            STATUS="${STATUS} ⚠️ Stale heartbeat"
        fi
    fi

    MESSAGE="${MESSAGE}• <b>${bot}</b>: ${STATUS}\n"
done

# Send via Telegram
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=${MESSAGE}" \
    -d "parse_mode=HTML" \
    -d "disable_notification=true" > /dev/null

echo "Daily check sent at $(date)"
