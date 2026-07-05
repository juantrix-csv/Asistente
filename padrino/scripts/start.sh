#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh — Start the Hermes Gateway service (Padrino Digital)
# ---------------------------------------------------------------------------
# Wrapper around systemctl start for hermes-gateway.service.
# Safe to run multiple times — systemd is idempotent on start.
#
# Usage:
#   sudo bash start.sh
# ---------------------------------------------------------------------------

set -Eeuo pipefail

readonly SERVICE="hermes-gateway"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

log()  { echo "[${TIMESTAMP}] $*"; }

main() {
    if [[ "$(id -u)" -ne 0 ]]; then
        echo "ERROR: This script must run as root (needed for systemctl)." >&2
        echo "Usage: sudo bash start.sh" >&2
        exit 1
    fi

    log "Starting ${SERVICE}..."
    if systemctl start "${SERVICE}"; then
        sleep 1
        local status
        status="$(systemctl is-active "${SERVICE}")"
        if [[ "${status}" == "active" ]]; then
            echo -e "${GREEN}✓${NC} ${SERVICE} is now active (running)"
        else
            echo -e "${RED}✗${NC} ${SERVICE} status is '${status}' — check: sudo systemctl status ${SERVICE}"
            exit 1
        fi
    else
        echo -e "${RED}✗${NC} Failed to start ${SERVICE}. Check: sudo journalctl -u ${SERVICE} -n 20"
        exit 1
    fi
}

main "$@"
