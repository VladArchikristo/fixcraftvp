#!/bin/bash
# Cron bot runner — executes AI and bash jobs for @kronikronikroni_bot
# Uses Haiku for AI jobs (cheap), bash for system jobs

set -euo pipefail

export HOME="/Users/vladimirprihodko"

# Load nvm for node access (needed by Claude CLI hooks)
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh" 2>/dev/null
fi

export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# macOS doesn't have GNU timeout — use bash replacement
run_with_timeout() {
    local timeout_secs="$1"
    shift
    "$@" &
    local cmd_pid=$!
    (
        sleep "$timeout_secs"
        kill "$cmd_pid" 2>/dev/null
    ) &
    local watchdog_pid=$!
    wait "$cmd_pid" 2>/dev/null
    local exit_code=$?
    kill "$watchdog_pid" 2>/dev/null
    wait "$watchdog_pid" 2>/dev/null
    return $exit_code
}

# Token loaded from config — NEVER hardcode secrets in scripts
CRON_SECRETS="$HOME/cron-secrets.conf"
if [ -f "$CRON_SECRETS" ]; then
    # shellcheck disable=SC1090
    source "$CRON_SECRETS"
fi
TELEGRAM_TOKEN="${CRON_BOT_TOKEN:-}"
CHAT_ID="${CRON_CHAT_ID:-244710532}"

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "$(date): ERROR — CRON_BOT_TOKEN not set in $CRON_SECRETS" >&2
    exit 1
fi
LOCK_DIR="/tmp/cron-locks"
LOG_DIR="$HOME/logs/cron"
RETRY_DIR="/tmp/cron-retry"

mkdir -p "$LOCK_DIR" "$LOG_DIR" "$RETRY_DIR"

send_telegram() {
    local text="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="$CHAT_ID" \
        -d text="$text" \
        -d parse_mode="Markdown" > /dev/null 2>&1
}

acquire_lock() {
    local job_name="$1"
    local lock_path="$LOCK_DIR/$job_name"
    if mkdir "$lock_path" 2>/dev/null; then
        echo $$ > "$lock_path/pid"
        echo "$(date +%s)" > "$lock_path/timestamp"
        return 0
    fi
    # Lock exists — check if stale (>5 min)
    local ts_file="$lock_path/timestamp"
    if [ -f "$ts_file" ]; then
        local ts=$(cat "$ts_file" 2>/dev/null || echo 0)
        local now_ts=$(date +%s)
        local age=$((now_ts - ts))
        if [ "$age" -gt 300 ]; then
            # Stale lock — kill old process and take over
            local old_pid=$(cat "$lock_path/pid" 2>/dev/null)
            [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null && kill "$old_pid" 2>/dev/null
            rm -rf "$lock_path"
            mkdir "$lock_path" 2>/dev/null || return 1
            echo $$ > "$lock_path/pid"
            echo "$(date +%s)" > "$lock_path/timestamp"
            return 0
        fi
    else
        # No timestamp = orphaned lock — clean up
        rm -rf "$lock_path"
        mkdir "$lock_path" 2>/dev/null || return 1
        echo $$ > "$lock_path/pid"
        echo "$(date +%s)" > "$lock_path/timestamp"
        return 0
    fi
    return 1
}

release_lock() {
    local job_name="$1"
    rm -rf "$LOCK_DIR/$job_name"
}

run_ai_job() {
    local job_name="$1"
    local prompt="$2"
    local job_timeout="${3:-300}"

    if ! acquire_lock "$job_name"; then
        echo "$(date): $job_name — locked, skipping" >> "$LOG_DIR/skipped.log"
        return 0
    fi

    echo "$(date): $job_name — starting (timeout=${job_timeout}s)" >> "$LOG_DIR/$job_name.log"

    local result
    result=$(run_with_timeout "$job_timeout" "$HOME/.local/bin/claude" -p "$prompt" --model claude-haiku-4-5 --output-format text 2>>"$LOG_DIR/$job_name.log") || {
        local exit_code=$?
        release_lock "$job_name"
        echo "$(date): $job_name — failed (exit=$exit_code)" >> "$LOG_DIR/$job_name.log"
        if [ $exit_code -eq 143 ]; then
            echo "$prompt" > "$RETRY_DIR/$job_name"
            echo "$(date): $job_name — timeout, queued for retry" >> "$LOG_DIR/errors.log"
        fi
        return 1
    }

    if [ -n "$result" ]; then
        send_telegram "🤖 *$job_name*
$result"
        echo "$(date): $job_name — success, sent to Telegram" >> "$LOG_DIR/$job_name.log"
    else
        echo "$(date): $job_name — empty result" >> "$LOG_DIR/$job_name.log"
    fi

    release_lock "$job_name"
}

run_bash_job() {
    local job_name="$1"
    shift

    if ! acquire_lock "$job_name"; then
        return 0
    fi

    "$@" 2>&1 | head -50
    echo "$(date): $job_name — done"
    release_lock "$job_name"
}

# === JOBS ===

job_monitor() {
    local status="📊 *Мониторинг* $(date '+%H:%M')\n"

    # Check FixCraft
    local http_code
    http_code=$(curl -s -L -o /dev/null -w "%{http_code}" --max-time 10 "https://fixcraftvp.com" 2>/dev/null) || http_code="ERR"
    if [ "$http_code" = "200" ]; then
        status+="✅ FixCraft: OK\n"
    else
        status+="❌ FixCraft: $http_code\n"
    fi

    # Check bots
    for bot_name in beast vasily masha kostya philip peter zina; do
        local hb_file="$HOME/logs/${bot_name}-heartbeat"
        if [ -f "$hb_file" ]; then
            local raw_hb=$(cat "$hb_file" 2>/dev/null)
            local last_hb
            # Handle both epoch timestamps and ISO dates (2026-04-06T09:24:50.478897)
            if echo "$raw_hb" | grep -qE '^[0-9]+$'; then
                last_hb=$raw_hb
            elif echo "$raw_hb" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T'; then
                # Strip fractional seconds and timezone, parse ISO date
                local clean_hb
                clean_hb=$(echo "$raw_hb" | sed 's/\.[0-9]*//' | sed 's/[+-][0-9:]*$//')
                last_hb=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_hb" +%s 2>/dev/null || echo 0)
            else
                last_hb=0
            fi
            local now=$(date +%s)
            local diff=$((now - last_hb))
            if [ $diff -lt 300 ]; then
                status+="✅ $bot_name: alive (${diff}s ago)\n"
            else
                status+="⚠️ $bot_name: stale (${diff}s)\n"
            fi
        else
            status+="❌ $bot_name: no heartbeat\n"
        fi
    done

    # Check Nexus
    if pgrep -f "claudeclaw.*start" > /dev/null 2>&1; then
        status+="✅ Nexus: running\n"
    else
        status+="❌ Nexus: not running\n"
    fi

    # Only alert if something is wrong
    if echo "$status" | grep -qE "❌|⚠️"; then
        send_telegram "$status"
    fi
    echo "$(date): monitor — done" >> "$LOG_DIR/monitor.log"
}

job_self_check() {
    local status="🔍 *Self-Check* $(date '+%H:%M')\n\n"
    local problems=""

    # Check bots via heartbeat files (reliable — updated every ~60s by live bots)
    for bot_entry in "Beast:beast" "Вася:vasily" "Маша:masha" "Костя:kostya" "Филип:philip" "Питер:peter" "Зина:zina"; do
        local label="${bot_entry%%:*}"
        local hb_name="${bot_entry##*:}"
        local hb_file="$HOME/logs/${hb_name}-heartbeat"
        if [ -f "$hb_file" ]; then
            local raw_hb=$(cat "$hb_file" 2>/dev/null)
            local last_hb
            if echo "$raw_hb" | grep -qE '^[0-9]+$'; then
                last_hb=$raw_hb
            elif echo "$raw_hb" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T'; then
                local clean_hb
                clean_hb=$(echo "$raw_hb" | sed 's/\.[0-9]*//' | sed 's/[+-][0-9:]*$//')
                last_hb=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_hb" +%s 2>/dev/null || echo 0)
            else
                last_hb=0
            fi
            local now=$(date +%s)
            local diff=$((now - last_hb))
            if [ $diff -lt 300 ]; then
                status+="✅ $label: alive (${diff}s ago)\n"
            elif [ $diff -lt 3600 ]; then
                status+="⚠️ $label: stale (${diff}s)\n"
                problems+="$label — нет ответа ${diff}с\n"
            else
                status+="❌ $label: мёртв\n"
                problems+="$label мёртв (нет heartbeat)\n"
            fi
        else
            status+="❌ $label: no heartbeat\n"
            problems+="$label — нет heartbeat файла\n"
        fi
    done

    # Check Nexus via launchctl
    local nexus_pid=$(launchctl list 2>/dev/null | grep claudeclaw | awk '{print $1}')
    if [ -n "$nexus_pid" ] && [ "$nexus_pid" != "-" ] && echo "$nexus_pid" | grep -qE '^[0-9]+$'; then
        status+="✅ Nexus: PID $nexus_pid\n"
    else
        status+="❌ Nexus\n"
        problems+="Nexus не запущен\n"
    fi

    # Disk & Logs
    local disk_usage=$(df -h / | awk 'NR==2{print $5}')
    local log_size=$(du -sh "$HOME/logs" 2>/dev/null | awk '{print $1}')
    status+="💾 Диск: $disk_usage | Логи: ${log_size:-?}\n"

    if [ -n "$problems" ]; then
        status+="\n⚠️ Есть проблемы!\n$problems"
        send_telegram "$status"
    fi
    echo "$(date): self-check — done" >> "$LOG_DIR/self-check.log"
}

job_auto_save() {
    # Copy Claude memory to Obsidian
    local obsidian="$HOME/ObsidianVault"
    if [ -d "$obsidian" ]; then
        local memory_src="$HOME/.claude/projects/-Users-vladimirprihodko------------fixcraftvp/memory"
        local memory_dst="$obsidian/Claude-Memory"
        mkdir -p "$memory_dst"
        if [ -d "$memory_src" ]; then
            cp -R "$memory_src/"* "$memory_dst/" 2>/dev/null
            echo "$(date): auto-save done" >> "$LOG_DIR/auto-save.log"
        fi
    fi
}

job_token_usage() {
    local status="📈 *System Stats* $(date '+%H:%M')\n"
    status+="⏱ Uptime: $(uptime | sed 's/.*up/up/')\n"
    local procs=$(ps aux | wc -l)
    status+="📊 Processes: $procs\n"
    send_telegram "$status"
}

job_memory_cleanup() {
    # Rotate old logs
    find "$HOME/logs" -name "*.log" -size +10M -exec truncate -s 1M {} \; 2>/dev/null
    find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null
    find "$LOCK_DIR" -maxdepth 1 -type d -mmin +10 -exec rm -rf {} \; 2>/dev/null
    echo "$(date): cleanup done" >> "$LOG_DIR/cleanup.log"
}

job_git_auto_save() {
    local status="💾 *Git Auto-Save* $(date '+%H:%M')\n"
    local saved=0

    # Save main fixcraftvp repo
    local main_repo="$HOME/Папка тест/fixcraftvp"
    if [ -d "$main_repo/.git" ]; then
        cd "$main_repo"
        if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
            git add -A 2>/dev/null
            git commit -m "auto-save: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null && {
                git push origin main 2>/dev/null
                status+="✅ fixcraftvp: committed & pushed\n"
                saved=$((saved + 1))
            }
        else
            status+="⏭ fixcraftvp: clean\n"
        fi
    fi

    # Save agents repo
    local agents_repo="$HOME/Папка тест/fixcraftvp/agents"
    if [ -d "$agents_repo/.git" ]; then
        cd "$agents_repo"
        if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
            git add -A 2>/dev/null
            git commit -m "auto-save: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null && {
                git push origin main 2>/dev/null
                status+="✅ agents: committed & pushed\n"
                saved=$((saved + 1))
            }
        else
            status+="⏭ agents: clean\n"
        fi
    fi

    if [ $saved -gt 0 ]; then
        send_telegram "$status"
    fi
    echo "$(date): git-auto-save done ($saved repos saved)" >> "$LOG_DIR/git-auto-save.log"
}

job_watchdog() {
    # Kill stale locks (>5 min old)
    for lock in "$LOCK_DIR"/*/; do
        [ -d "$lock" ] || continue
        local ts_file="$lock/timestamp"
        if [ -f "$ts_file" ]; then
            local ts=$(cat "$ts_file")
            local now=$(date +%s)
            if [ $((now - ts)) -gt 300 ]; then
                local pid_file="$lock/pid"
                if [ -f "$pid_file" ]; then
                    kill -9 "$(cat "$pid_file")" 2>/dev/null
                fi
                rm -rf "$lock"
                echo "$(date): killed stale lock $(basename "$lock")" >> "$LOG_DIR/watchdog.log"
            fi
        fi
    done

    # Retry failed AI jobs
    for retry_file in "$RETRY_DIR"/*; do
        [ -f "$retry_file" ] || continue
        local job_name=$(basename "$retry_file")
        local prompt=$(cat "$retry_file")
        rm "$retry_file"
        run_ai_job "retry-$job_name" "$prompt" 300
    done
}


job_news_digest() {
    # Pure bash — no Claude CLI needed
    # Crypto prices from CoinGecko free API
    local status="📰 *Дайджест* $(date '+%H:%M')\n\n"

    # Crypto prices
    local prices
    prices=$(curl -s --max-time 15 "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true" 2>/dev/null)
    if [ -n "$prices" ] && echo "$prices" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
        local btc=$(echo "$prices" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"BTC: \${d['bitcoin']['usd']:,.0f} ({d['bitcoin']['usd_24h_change']:+.1f}%)\")" 2>/dev/null)
        local eth=$(echo "$prices" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"ETH: \${d['ethereum']['usd']:,.0f} ({d['ethereum']['usd_24h_change']:+.1f}%)\")" 2>/dev/null)
        local sol=$(echo "$prices" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"SOL: \${d['solana']['usd']:,.1f} ({d['solana']['usd_24h_change']:+.1f}%)\")" 2>/dev/null)
        status+="💰 $btc\n💰 $eth\n💰 $sol\n"
    else
        status+="💰 Крипто: API недоступен\n"
    fi

    # Fear & Greed index
    local fng
    fng=$(curl -s --max-time 10 "https://api.alternative.me/fng/?limit=1" 2>/dev/null)
    if [ -n "$fng" ]; then
        local fng_val=$(echo "$fng" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['data'][0]['value']} — {d['data'][0]['value_classification']}\")" 2>/dev/null)
        [ -n "$fng_val" ] && status+="😱 Fear/Greed: $fng_val\n"
    fi

    # System uptime
    local up=$(uptime | sed 's/.*up /up /' | sed 's/,.*//')
    status+="\n🖥 Mac Mini: $up"

    send_telegram "$status"
}

job_daily_report() {
    # Pure bash — evening summary from today's logs
    local status="📊 *Вечерний отчёт* $(date '+%d.%m %H:%M')\n\n"
    local today=$(date '+%b %_d')

    # Bot status
    local alive=0 dead=0
    for bot_entry in "Beast:beast" "Вася:vasily" "Маша:masha" "Костя:kostya" "Филип:philip" "Питер:peter" "Зина:zina"; do
        local label="${bot_entry%%:*}"
        local hb_name="${bot_entry##*:}"
        local hb_file="$HOME/logs/${hb_name}-heartbeat"
        if [ -f "$hb_file" ]; then
            local raw_hb=$(cat "$hb_file" 2>/dev/null)
            local last_hb
            if echo "$raw_hb" | grep -qE '^[0-9]+$'; then
                last_hb=$raw_hb
            elif echo "$raw_hb" | grep -qE '^[0-9]{4}-'; then
                local clean_hb=$(echo "$raw_hb" | sed 's/\.[0-9]*//' | sed 's/[+-][0-9:]*$//')
                last_hb=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_hb" +%s 2>/dev/null || echo 0)
            else
                last_hb=0
            fi
            local now=$(date +%s)
            if [ $((now - last_hb)) -lt 300 ]; then
                alive=$((alive + 1))
            else
                dead=$((dead + 1))
                status+="⚠️ $label — stale\n"
            fi
        else
            dead=$((dead + 1))
            status+="❌ $label — нет heartbeat\n"
        fi
    done
    status+="🤖 Боты: ${alive} живых"
    [ $dead -gt 0 ] && status+=", ${dead} проблемных"
    status+="\n"

    # Cron errors today
    local cron_errors=0
    for log in "$LOG_DIR"/*.log; do
        [ -f "$log" ] || continue
        local errs=$(grep -c "failed\|ERROR" "$log" 2>/dev/null | grep "$today" 2>/dev/null || echo 0)
        cron_errors=$((cron_errors + errs))
    done

    # Git commits today
    local git_commits=0
    if [ -d "$HOME/Папка тест/fixcraftvp/.git" ]; then
        git_commits=$(cd "$HOME/Папка тест/fixcraftvp" && git log --oneline --since="midnight" 2>/dev/null | wc -l | tr -d ' ')
    fi
    status+="📝 Git коммитов сегодня: $git_commits\n"

    # Disk usage
    local disk=$(df -h / | awk 'NR==2{print $5}')
    local log_size=$(du -sh "$HOME/logs" 2>/dev/null | awk '{print $1}')
    status+="💾 Диск: $disk | Логи: ${log_size:-?}"

    send_telegram "$status"
}

job_security_scan() {
    # Pure bash — no Claude CLI, direct system checks
    local status="🔒 *Security Scan* $(date '+%H:%M')\n\n"
    local issues=0

    # 1. Check for suspicious processes (crypto miners, etc)
    local sus_procs=$(ps aux | grep -iE "xmrig|cryptonight|minerd|coinhive|kworker.*mining" | grep -v grep | wc -l | tr -d ' ')
    if [ "$sus_procs" -gt 0 ]; then
        status+="🚨 Подозрительные процессы: $sus_procs\n"
        issues=$((issues + 1))
    else
        status+="✅ Процессы: чисто\n"
    fi

    # 2. Check listening ports
    local open_ports=$(lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | awk 'NR>1{print $1":"$9}' | sort -u | head -10)
    local port_count=$(echo "$open_ports" | grep -c "." 2>/dev/null || echo 0)
    status+="🌐 Открытых портов: $port_count\n"

    # 3. Check SSH attempts (if log exists)
    local ssh_fails=0
    if [ -f /var/log/system.log ]; then
        ssh_fails=$(grep -c "sshd.*Failed" /var/log/system.log 2>/dev/null | tr -d "[:space:]" || echo 0)
        [[ "$ssh_fails" =~ ^[0-9]+$ ]] || ssh_fails=0
    fi
    if [ "$ssh_fails" -gt 0 ]; then
        status+="⚠️ SSH failed attempts: $ssh_fails\n"
        issues=$((issues + 1))
    else
        status+="✅ SSH: чисто\n"
    fi

    # 4. Check for recently modified files in sensitive dirs
    local recent_sensitive=$(find /usr/local/bin /usr/bin -newer "$HOME/.bashrc" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$recent_sensitive" -gt 0 ]; then
        status+="⚠️ Изменений в /usr/*/bin: $recent_sensitive файлов\n"
        issues=$((issues + 1))
    else
        status+="✅ Системные бинарники: не изменены\n"
    fi

    # 5. Check .env files for world-readable
    local world_readable=$(find "$HOME/Папка тест/fixcraftvp" -name ".env" -perm +004 2>/dev/null | wc -l | tr -d ' ')
    if [ "$world_readable" -gt 0 ]; then
        status+="⚠️ .env файлы world-readable: $world_readable\n"
        issues=$((issues + 1))
    fi

    if [ $issues -eq 0 ]; then
        status+="\n✅ Всё чисто"
    else
        status+="\n⚠️ Найдено проблем: $issues"
    fi

    send_telegram "$status"
}

# === MAIN ===
JOB="${1:-}"

case "$JOB" in
    watchdog) run_bash_job watchdog job_watchdog ;;
    monitor) run_bash_job monitor job_monitor ;;
    self-check) run_bash_job self-check job_self_check ;;
    auto-save) run_bash_job auto-save job_auto_save ;;
    token-usage) run_bash_job token-usage job_token_usage ;;
    memory-cleanup) run_bash_job memory-cleanup job_memory_cleanup ;;
    git-auto-save) run_bash_job git-auto-save job_git_auto_save ;;
    news-digest)
        run_bash_job news-digest job_news_digest
        ;;
    daily-report)
        run_bash_job daily-report job_daily_report
        ;;
    security-scan)
        run_bash_job security-scan job_security_scan
        ;;
    *)
        echo "Usage: $0 {watchdog|monitor|self-check|auto-save|token-usage|memory-cleanup|git-auto-save|news-digest|daily-report|security-scan}"
        exit 1
        ;;
esac
