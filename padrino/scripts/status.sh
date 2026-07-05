#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# status.sh — Show Hermes Gateway service status (Padrino Digital)
# ---------------------------------------------------------------------------
# Displays systemctl status, active state, enabled state, uptime,
# and recent log entries for hermes-gateway.service.
#
# Usage:
#   bash status.sh           # full status
#   bash status.sh --short   # one-line summary only
# ---------------------------------------------------------------------------

set -Eeuo pipefail

readonly SERVICE="hermes-gateway"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

log()  { echo "[${TIMESTAMP}] $*"; }

print_short() {
    local active enabled
    active="$(systemctl is-active "${SERVICE}" 2>/dev/null || echo 'unknown')"
    enabled="$(systemctl is-enabled "${SERVICE}" 2>/dev/null || echo 'unknown')"

    local color="${GREEN}"
    [[ "${active}" != "active" ]] && color="${RED}"

    echo -e "${color}[${SERVICE}]${NC} active=${active} enabled=${enabled}"
}

print_full() {
    echo ""
    echo -e "${CYAN}━━━ Hermes Gateway Status ━━━${NC}"
    echo ""

    # Active state
    local active
    active="$(systemctl is-active "${SERVICE}" 2>/dev/null || echo 'unknown')"
    if [[ "${active}" == "active" ]]; then
        echo -e "  Status:   ${GREEN}${active}${NC} (running)"
    elif [[ "${active}" == "inactive" ]]; then
        echo -e "  Status:   ${YELLOW}${active}${NC} (stopped)"
    else
        echo -e "  Status:   ${RED}${active}${NC}"
    fi

    # Enabled state
    local enabled
    enabled="$(systemctl is-enabled "${SERVICE}" 2>/dev/null || echo 'unknown')"
    if [[ "${enabled}" == "enabled" ]]; then
        echo -e "  Boot:     ${GREEN}${enabled}${NC} (starts on boot)"
    else
        echo -e "  Boot:     ${YELLOW}${enabled}${NC} (NOT starting on boot)"
    fi

    # Uptime / process info
    if [[ "${active}" == "active" ]]; then
        local pid
        pid="$(systemctl show -p MainPID --value "${SERVICE}" 2>/dev/null || echo '')"
        if [[ -n "${pid}" && "${pid}" != "0" ]]; then
            echo -e "  PID:      ${pid}"
            local elapsed
            elapsed="$(ps -o etime= -p "${pid}" 2>/dev/null | xargs || echo '?')"
            echo -e "  Uptime:   ${elapsed}"
        fi
    fi

    echo ""

    # Recent log entries
    if command -v journalctl &>/dev/null; then
        echo -e "${CYAN}  Recent logs (last 10 lines):${NC}"
        journalctl -u "${SERVICE}" -n 10 --no-pager 2>/dev/null | sed 's/^/    /' || echo "    (no logs available)"
    fi

    echo ""
}

main() {
    if [[ "${1:-}" == "--short" ]]; then
        print_short
    else
        print_full
    fi
}

main "$@"
