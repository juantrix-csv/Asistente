#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# healthcheck.sh — Padrino Digital health check
# ---------------------------------------------------------------------------
# Verifies:
#   1. Hermes gateway process is running (systemd active)
#   2. Telegram connectivity (bot responds to API call)
#   3. Disk space above threshold
#   4. Padrino data directories accessible
#
# Usage:
#   sudo -u padrino bash healthcheck.sh
#
# Exit codes:
#   0 — all checks passed (healthy)
#   1 — one or more checks failed (unhealthy)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
readonly SERVICE="hermes-gateway"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_BACKUPS="/srv/padrino/backups"
readonly PADRINO_LOGS="/srv/padrino/logs"

# Thresholds
readonly DISK_WARN_PCT=85
readonly DISK_CRIT_PCT=95
readonly MIN_DISK_GB=1

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

FAILURES=0

log()   { echo -e "[${TIMESTAMP}] $*"; }
pass()  { echo -e "  ${GREEN}✓ PASS${NC} — $*"; }
warn()  { echo -e "  ${YELLOW}⚠ WARN${NC} — $*"; }
fail()  { ((FAILURES++)); echo -e "  ${RED}✗ FAIL${NC} — $*"; }

# ---------------------------------------------------------------------------
# Check 1: Hermes gateway process running
# ---------------------------------------------------------------------------
check_gateway_process() {
    echo -e "\n${CYAN}[1/4] Hermes Gateway Process${NC}"

    if ! command -v systemctl &>/dev/null; then
        warn "systemctl not available — cannot check service state"
        return
    fi

    local status
    status="$(systemctl is-active "${SERVICE}" 2>/dev/null || echo 'inactive')"

    if [[ "${status}" == "active" ]]; then
        pass "hermes-gateway.service is active (running)"
    else
        fail "hermes-gateway.service is ${status} — should be active"
    fi
}

# ---------------------------------------------------------------------------
# Check 2: Telegram connectivity
# ---------------------------------------------------------------------------
check_telegram() {
    echo -e "\n${CYAN}[2/4] Telegram Connectivity${NC}"

    local token=""
    # Try reading the token from standard locations
    if [[ -f /home/padrino/.hermes/.env ]]; then
        token="$(grep -E '^TELEGRAM_BOT_TOKEN=' /home/padrino/.hermes/.env 2>/dev/null | cut -d= -f2- | xargs || echo '')"
    elif [[ -f /home/padrino/.hermes/secrets.env ]]; then
        token="$(grep -E '^TELEGRAM_BOT_TOKEN=' /home/padrino/.hermes/secrets.env 2>/dev/null | cut -d= -f2- | xargs || echo '')"
    fi

    if [[ -z "${token}" ]]; then
        warn "TELEGRAM_BOT_TOKEN not found — skipping connectivity check"
        warn "  Expected in: /home/padrino/.hermes/.env"
        return
    fi

    # Test Telegram API connectivity
    local response
    response="$(curl -s --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null || echo '')"

    if echo "${response}" | grep -q '"ok":true'; then
        local bot_username
        bot_username="$(echo "${response}" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)"
        pass "Telegram API reachable — bot @${bot_username:-unknown}"
    elif echo "${response}" | grep -q '"error_code"'; then
        local err_desc
        err_desc="$(echo "${response}" | grep -o '"description":"[^"]*"' | cut -d'"' -f4)"
        fail "Telegram API error: ${err_desc:-unknown error}"
    else
        fail "Cannot reach Telegram API (network issue or invalid token)"
    fi
}

# ---------------------------------------------------------------------------
# Check 3: Disk space
# ---------------------------------------------------------------------------
check_disk_space() {
    echo -e "\n${CYAN}[3/4] Disk Space${NC}"

    # Check the /srv/padrino mount point or root filesystem
    local mount
    mount="$(df -h "${PADRINO_DATA}" 2>/dev/null | tail -1 || df -h / | tail -1)"

    local total used avail pct
    total="$(echo "${mount}" | awk '{print $2}')"
    used="$(echo "${mount}" | awk '{print $3}')"
    avail="$(echo "${mount}" | awk '{print $4}')"
    pct="$(echo "${mount}" | awk '{print $5}' | tr -d '%')"

    echo "  Filesystem: total=${total} used=${used} avail=${avail} use=${pct}%"

    if (( pct >= DISK_CRIT_PCT )); then
        fail "Disk usage at ${pct}% (critical threshold: ${DISK_CRIT_PCT}%)"
    elif (( pct >= DISK_WARN_PCT )); then
        warn "Disk usage at ${pct}% (warning threshold: ${DISK_WARN_PCT}%)"
    else
        pass "Disk usage at ${pct}% — within limits"
    fi

    # Check minimum available space
    local avail_kb
    avail_kb="$(df -k "${PADRINO_DATA}" 2>/dev/null | tail -1 | awk '{print $4}' || df -k / | tail -1 | awk '{print $4}')"
    local avail_gb=$((avail_kb / 1024 / 1024))
    if (( avail_gb < MIN_DISK_GB )); then
        fail "Available disk space is ${avail_gb}GB (minimum: ${MIN_DISK_GB}GB)"
    fi
}

# ---------------------------------------------------------------------------
# Check 4: Padrino directories accessible
# ---------------------------------------------------------------------------
check_directories() {
    echo -e "\n${CYAN}[4/4] Padrino Directories${NC}"

    local dirs=(
        "${PADRINO_DATA}"
        "${PADRINO_DATA}/memory"
        "${PADRINO_DATA}/memory/areas"
        "${PADRINO_DATA}/memory/projects"
        "${PADRINO_DATA}/journal"
        "${PADRINO_DATA}/inbox"
        "${PADRINO_DATA}/exports"
        "${PADRINO_BACKUPS}"
        "${PADRINO_LOGS}"
    )

    for dir in "${dirs[@]}"; do
        if [[ -d "${dir}" ]]; then
            if [[ -r "${dir}" ]]; then
                if [[ -w "${dir}" ]]; then
                    pass "Accessible (rw): ${dir}"
                else
                    fail "Directory exists but NOT WRITABLE: ${dir}"
                fi
            else
                fail "Directory exists but NOT READABLE: ${dir}"
            fi
        else
            fail "Directory MISSING: ${dir} — run setup.sh"
        fi
    done
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "=============================================="
    echo "  Padrino Digital — Healthcheck Summary"
    echo "=============================================="
    echo ""

    if (( FAILURES == 0 )); then
        echo -e "  ${GREEN}Verdict: HEALTHY${NC} — all checks passed"
        echo ""
        exit 0
    else
        echo -e "  ${RED}Verdict: UNHEALTHY${NC} — ${FAILURES} check(s) failed"
        echo ""
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    log "Padrino Digital healthcheck starting..."
    echo ""

    check_gateway_process
    check_telegram
    check_disk_space
    check_directories
    print_summary
}

main "$@"
