#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Cron Subagent — Bot Health Monitor
# Standalone lightweight agent. Runs independently, outputs report.
# Designed to be called by Hermes cronjob once per hour.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

LOG_DIR="${HOME}/logs"
REPORT=""
ALERT_COUNT=0
UP_COUNT=0
DOWN_COUNT=0

# ── Header ─────────────────────────────────────────────────────
TIME_STR=$(date '+%H:%M %d.%m.%Y')
REPORT="📊 <b>Ежечасная сводка ботов</b>
🕐 ${TIME_STR}
"

# ── Bot registry (order matters) ───────────────────────────────
declare -a BOTS=(
    "beast:Beast"
    "kostya:Костя"
    "masha:Маша"
    "vasily:Василий"
    "philip:Филип"
    "peter:Пётр"
    "zina:Зина"
    "alexey:Алексей"
)

for entry in "${BOTS[@]}"; do
    KEY="${entry%%:*}"
    NAME="${entry#*:}"
    PID_FILE="${LOG_DIR}/${KEY}-bot.pid"
    HEARTBEAT="${LOG_DIR}/${KEY}-heartbeat"

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
            UPTIME=$(ps -p "$PID" -o etime= 2>/dev/null | tr -d ' ')
            MEM_MB=$(ps -p "$PID" -o rss= 2>/dev/null | awk '{printf "%.0f", $1/1024}')
            STATUS="✅ ${UPTIME}"
            [ -n "$MEM_MB" ] && STATUS="${STATUS} • ${MEM_MB}MB"
            ((UP_COUNT++))

            # Heartbeat freshness check
            if [ -f "$HEARTBEAT" ]; then
                HB_TIME=$(stat -f%Sm -t %s "$HEARTBEAT" 2>/dev/null || stat -c%Y "$HEARTBEAT")
                HB_AGE=$(( $(date +%s) - HB_TIME ))
                if [ "$HB_AGE" -gt 600 ]; then
                    STATUS="${STATUS} ⚠️ heartbeat ${HB_AGE}s"
                    ((ALERT_COUNT++))
                fi
            fi
        else
            STATUS="❌ МЁРТВ (PID ${PID})"
            ((DOWN_COUNT++))
            ((ALERT_COUNT++))
        fi
    else
        STATUS="⚠️ НЕТ PID-ФАЙЛА"
        ((DOWN_COUNT++))
        ((ALERT_COUNT++))
    fi

    REPORT="${REPORT}
• <b>${NAME}</b>: ${STATUS}"
done

# ── Footer ─────────────────────────────────────────────────────
REPORT="${REPORT}

📈 <b>Итого:</b> ${UP_COUNT} живых / ${DOWN_COUNT} мёртвых"

if [ "$ALERT_COUNT" -gt 0 ]; then
    REPORT="${REPORT}
🔔 <b>Требуется внимание:</b> ${ALERT_COUNT} проблем(ы)"
fi

# ── Output ─────────────────────────────────────────────────────
echo "$REPORT"
