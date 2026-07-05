#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# stop.sh — Stop the Hermes Gateway service (Padrino Digital)
# ---------------------------------------------------------------------------
# Wrapper around systemctl stop for hermes-gateway.service.
# Safe to run when the service is already stopped.
#
# Usage:
#   sudo bash stop.sh
# ---------------------------------------------------------------------------

set -Eeuo pipefail

readonly SERVICE="hermes-gateway"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# Colors
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

log()  { echo "[${TIMESTAMP}] $*"; }

main() {
    if [[ "$(id -u)" -ne 0 ]]; then
        echo "ERROR: This script must run as root (needed for systemctl)." >&2
        echo "Usage: sudo bash stop.sh" >&2
        exit 1
    fi

    local status
    status="$(systemctl is-active "${SERVICE}" 2>/dev/null || echo 'inactive')"

    if [[ "${status}" != "active" ]]; then
        echo -e "${YELLOW}⚠${NC} ${SERVICE} is already inactive (status: ${status})"
        exit 0
    fi

    log "Stopping ${SERVICE}..."
    if systemctl stop "${SERVICE}"; then
        sleep 1
        echo -e "${GREEN}✓${NC} ${SERVICE} stopped successfully"
    else
        echo "Failed to stop ${SERVICE}." >&2
        exit 1
    fi
}

main "$@"
