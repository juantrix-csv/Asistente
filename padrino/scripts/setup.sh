#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh — Padrino Digital initial system setup
# ---------------------------------------------------------------------------
# Idempotent. Safe to run multiple times. Debian/Ubuntu only.
#
# What it does:
#   1. Creates the 'padrino' system user (no sudo, SSH-key only)
#   2. Sets restrictive umask 077
#   3. Creates /srv/padrino/ directory tree with correct ownership
#   4. Validates dependencies (Python 3.11+, SQLite 3.35+ with FTS5)
#   5. Installs Hermes Agent v0.18.0 from Nous Research repo
#   6. Configures and enables the Hermes gateway systemd service
#   7. Enables UFW firewall (SSH + gateway port only)
#
# Usage:
#   sudo bash setup.sh
#
# Environment variables (optional):
#   HERMES_GATEWAY_PORT  — port for Telegram gateway (default: 8443)
#   HERMES_INSTALL_DIR   — Hermes install path (default: /home/padrino/hermes-agent)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# VPS data root (deployment target, independent of git checkout location)
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_BACKUPS="/srv/padrino/backups"
readonly PADRINO_ROOT="/srv/padrino"

# User
readonly PADRINO_USER="padrino"
readonly PADRINO_HOME="/home/${PADRINO_USER}"

# Hermes
readonly HERMES_VERSION="v0.18.0"
readonly HERMES_REPO="https://github.com/NousResearch/Hermes-Function-Calling.git"
readonly HERMES_INSTALL_DIR="${HERMES_INSTALL_DIR:-${PADRINO_HOME}/hermes-agent}"

# Gateway
readonly GATEWAY_PORT="${HERMES_GATEWAY_PORT:-8443}"

# Dependencies
readonly MIN_PYTHON_MAJOR=3
readonly MIN_PYTHON_MINOR=11
readonly MIN_SQLITE_VERSION="3.35.0"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log()  { echo -e "[${TIMESTAMP}] $*"; }
info() { log "${GREEN}[INFO]${NC} $*"; }
warn() { log "${YELLOW}[WARN]${NC} $*"; }
err()  { log "${RED}[ERROR]${NC} $*" >&2; }
die()  { err "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Preflight — must be root
# ---------------------------------------------------------------------------
preflight() {
    if [[ "$(id -u)" -ne 0 ]]; then
        die "This script must run as root. Use: sudo bash setup.sh"
    fi
    info "Preflight checks passed (running as root)"
}

# ---------------------------------------------------------------------------
# Detect VPS OS
# ---------------------------------------------------------------------------
detect_os() {
    if [[ ! -f /etc/os-release ]]; then
        die "Cannot detect OS — /etc/os-release not found. Debian/Ubuntu required."
    fi
    source /etc/os-release
    if [[ "${ID:-}" != "debian" && "${ID:-}" != "ubuntu" ]]; then
        die "Unsupported OS: ${ID:-unknown}. Debian or Ubuntu required."
    fi
    info "OS detected: ${PRETTY_NAME:-${ID}}"
}

# ---------------------------------------------------------------------------
# Create padrino system user (idempotent)
# ---------------------------------------------------------------------------
create_padrino_user() {
    if id "${PADRINO_USER}" &>/dev/null; then
        info "User '${PADRINO_USER}' already exists — skipping creation"
    else
        info "Creating system user: ${PADRINO_USER}"
        useradd -m -s /bin/bash "${PADRINO_USER}"
        info "User '${PADRINO_USER}' created (uid=$(id -u ${PADRINO_USER}))"
    fi

    # Enforce restrictive umask in .bashrc (idempotent)
    local bashrc="${PADRINO_HOME}/.bashrc"
    if ! grep -q 'umask 077' "${bashrc}" 2>/dev/null; then
        echo 'umask 077' >> "${bashrc}"
        info "umask 077 appended to ${bashrc}"
    else
        info "umask 077 already set in ${bashrc}"
    fi

    # Ensure padrino is NOT in sudo/wheel groups
    for grp in sudo wheel admin; do
        if groups "${PADRINO_USER}" 2>/dev/null | grep -q "\b${grp}\b"; then
            warn "Padrino user is in '${grp}' group — REMOVING (security policy)"
            gpasswd -d "${PADRINO_USER}" "${grp}" || warn "Could not remove from ${grp}"
        fi
    done

    info "User '${PADRINO_USER}' security: no sudo/wheel, key-only SSH recommended"
}

# ---------------------------------------------------------------------------
# Create data directory tree (idempotent)
# ---------------------------------------------------------------------------
create_directories() {
    local dirs=(
        "${PADRINO_DATA}/memory/areas"
        "${PADRINO_DATA}/memory/projects"
        "${PADRINO_DATA}/journal"
        "${PADRINO_DATA}/inbox"
        "${PADRINO_DATA}/exports"
        "${PADRINO_BACKUPS}"
        "${PADRINO_ROOT}/reports/daily"
        "${PADRINO_ROOT}/reports/weekly"
        "${PADRINO_ROOT}/reports/monthly"
        "${PADRINO_ROOT}/reports/code-audits"
        "${PADRINO_ROOT}/scripts"
        "${PADRINO_ROOT}/config"
        "${PADRINO_ROOT}/logs"
        "${PADRINO_ROOT}/tests"
        "${PADRINO_ROOT}/docs"
        "${PADRINO_ROOT}/skills"
    )

    for dir in "${dirs[@]}"; do
        mkdir -p "${dir}"
    done

    # Set ownership
    chown -R "${PADRINO_USER}:${PADRINO_USER}" "${PADRINO_ROOT}"
    # Restrictive permissions on data and backups
    chmod 750 "${PADRINO_ROOT}" "${PADRINO_DATA}" "${PADRINO_BACKUPS}"
    find "${PADRINO_DATA}" -type d -exec chmod 750 {} \;

    info "Directory tree created under ${PADRINO_ROOT}"
}

# ---------------------------------------------------------------------------
# Validate Python 3.11+
# ---------------------------------------------------------------------------
check_python() {
    if ! command -v python3 &>/dev/null; then
        die "python3 not found. Install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+."
    fi

    local py_ver
    py_ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    local py_major="${py_ver%%.*}"
    local py_minor="${py_ver#*.}"

    if (( py_major < MIN_PYTHON_MAJOR || (py_major == MIN_PYTHON_MAJOR && py_minor < MIN_PYTHON_MINOR) )); then
        die "Python ${py_ver} found — minimum required is ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}"
    fi
    info "Python ${py_ver} — OK"
}

# ---------------------------------------------------------------------------
# Validate SQLite 3.35+ with FTS5
# ---------------------------------------------------------------------------
check_sqlite() {
    if ! command -v sqlite3 &>/dev/null; then
        die "sqlite3 not found. Install sqlite3 >= ${MIN_SQLITE_VERSION}."
    fi

    local sql_ver
    sql_ver="$(sqlite3 --version | head -1 | awk '{print $1}')"

    # Compare version strings
    local lowest
    lowest="$(printf '%s\n' "${MIN_SQLITE_VERSION}" "${sql_ver}" | sort -V | head -1)"
    if [[ "${lowest}" != "${MIN_SQLITE_VERSION}" ]]; then
        die "SQLite ${sql_ver} found — minimum required is ${MIN_SQLITE_VERSION}"
    fi

    # Check FTS5 support
    if ! sqlite3 :memory: 'CREATE VIRTUAL TABLE fts_test USING fts5(x);' 2>/dev/null; then
        die "SQLite ${sql_ver} compiled WITHOUT FTS5 support. Reinstall with FTS5 enabled."
    fi

    info "SQLite ${sql_ver} with FTS5 — OK"
}

# ---------------------------------------------------------------------------
# Install Hermes Agent v0.18.0 (idempotent)
# ---------------------------------------------------------------------------
install_hermes() {
    if [[ -f "${HERMES_INSTALL_DIR}/hermes" ]] && "${HERMES_INSTALL_DIR}/hermes" --version 2>/dev/null | grep -q "${HERMES_VERSION}"; then
        info "Hermes ${HERMES_VERSION} already installed at ${HERMES_INSTALL_DIR}"
        return 0
    fi

    info "Installing Hermes Agent ${HERMES_VERSION} from ${HERMES_REPO}"

    # Install git if missing
    if ! command -v git &>/dev/null; then
        info "Installing git..."
        apt-get update -qq && apt-get install -y -qq git
    fi

    # Clone repo as padrino user to correct home
    if [[ -d "${HERMES_INSTALL_DIR}" ]]; then
        warn "Hermes directory exists but version mismatch; backing up to ${HERMES_INSTALL_DIR}.bak"
        mv "${HERMES_INSTALL_DIR}" "${HERMES_INSTALL_DIR}.bak.$(date +%s)"
    fi

    sudo -u "${PADRINO_USER}" git clone --depth 1 --branch "${HERMES_VERSION}" \
        "${HERMES_REPO}" "${HERMES_INSTALL_DIR}"

    # Install Python dependencies
    if [[ -f "${HERMES_INSTALL_DIR}/requirements.txt" ]]; then
        sudo -u "${PADRINO_USER}" pip3 install --user -r "${HERMES_INSTALL_DIR}/requirements.txt"
    fi

    # Ensure hermes is in PATH for padrino user
    local bashrc="${PADRINO_HOME}/.bashrc"
    local path_line='export PATH="$HOME/.local/bin:$PATH"'
    if ! grep -qF "${path_line}" "${bashrc}" 2>/dev/null; then
        echo "${path_line}" >> "${bashrc}"
    fi

    info "Hermes ${HERMES_VERSION} installed at ${HERMES_INSTALL_DIR}"
}

# ---------------------------------------------------------------------------
# Setup Hermes gateway systemd service
# ---------------------------------------------------------------------------
setup_systemd() {
    local service_file="/etc/systemd/system/hermes-gateway.service"
    local src_service="${PROJECT_ROOT}/config/padrino-gateway.service"

    if [[ ! -f "${src_service}" ]]; then
        warn "Systemd template not found at ${src_service} — skipping service setup"
        return 0
    fi

    cp "${src_service}" "${service_file}"
    chmod 644 "${service_file}"

    systemctl daemon-reload
    systemctl enable hermes-gateway.service

    info "Systemd service installed and enabled: hermes-gateway.service"
}

# ---------------------------------------------------------------------------
# Configure UFW firewall
# ---------------------------------------------------------------------------
configure_firewall() {
    if ! command -v ufw &>/dev/null; then
        info "Installing ufw..."
        apt-get update -qq && apt-get install -y -qq ufw
    fi

    # Idempotent: ensure rules exist
    ufw --force reset >/dev/null 2>&1 || true
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    ufw allow 22/tcp comment 'SSH' >/dev/null
    ufw allow "${GATEWAY_PORT}/tcp" comment 'Hermes Gateway' >/dev/null

    if ufw status | grep -q "^Status: active"; then
        info "UFW already active — reloading rules"
        ufw reload >/dev/null
    else
        info "Enabling UFW..."
        ufw --force enable >/dev/null
    fi

    info "UFW firewall configured: SSH (22) + Gateway (${GATEWAY_PORT})"
}

# ---------------------------------------------------------------------------
# Print final summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "=============================================="
    echo "  Padrino Digital — Setup Complete"
    echo "=============================================="
    echo ""
    echo "  User:          ${PADRINO_USER} (uid=$(id -u ${PADRINO_USER} 2>/dev/null || echo '?'))"
    echo "  Data root:     ${PADRINO_ROOT}"
    echo "  Hermes dir:    ${HERMES_INSTALL_DIR}"
    echo "  Gateway port:  ${GATEWAY_PORT}"
    echo ""
    echo "Next steps:"
    echo "  1. Copy config/.env.template to ${PADRINO_HOME}/.hermes/.env"
    echo "  2. Fill in TELEGRAM_BOT_TOKEN and model API keys"
    echo "  3. chmod 600 ${PADRINO_HOME}/.hermes/.env"
    echo "  4. systemctl start hermes-gateway"
    echo "  5. systemctl status hermes-gateway"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    log "Padrino Digital setup starting..."
    echo ""

    preflight
    detect_os
    create_padrino_user
    create_directories
    check_python
    check_sqlite
    install_hermes
    setup_systemd
    configure_firewall
    print_summary

    info "Setup completed successfully."
}

main "$@"
