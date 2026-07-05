#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# security-audit.sh — Padrino Digital security baseline audit
# ---------------------------------------------------------------------------
# Run on the VPS before and after Padrino Digital deployment.
# Checks user, permissions, SSH, firewall, secrets, and sensitive paths.
#
# Usage:
#   sudo bash security-audit.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed (warnings)
#   2 — critical failure (must fix before proceeding)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
readonly PADRINO_USER="padrino"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_HOME="/home/${PADRINO_USER}"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

PASS=0
WARN=0
FAIL=0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
header() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }
pass()  { ((PASS++)); echo -e "  ${GREEN}✓ PASS${NC} — $*"; }
warn()  { ((WARN++)); echo -e "  ${YELLOW}⚠ WARN${NC} — $*"; }
fail()  { ((FAIL++)); echo -e "  ${RED}✗ FAIL${NC} — $*"; }

# ---------------------------------------------------------------------------
# Check: running as root
# ---------------------------------------------------------------------------
check_root() {
    header "Preflight"
    if [[ "$(id -u)" -eq 0 ]]; then
        pass "Running as root (can check all users)"
    else
        warn "Not running as root — some checks may be incomplete. Use: sudo bash security-audit.sh"
    fi
}

# ---------------------------------------------------------------------------
# Check: dedicated padrino user exists
# ---------------------------------------------------------------------------
check_padrino_user() {
    header "User: ${PADRINO_USER}"
    if id "${PADRINO_USER}" &>/dev/null; then
        local uid
        uid="$(id -u "${PADRINO_USER}")"
        pass "User '${PADRINO_USER}' exists (uid=${uid})"

        if (( uid < 1000 )); then
            fail "UID ${uid} < 1000 — should be a regular (non-system) user"
        else
            pass "UID ${uid} >= 1000 — regular user"
        fi
    else
        fail "User '${PADRINO_USER}' does NOT exist. Run setup.sh first."
    fi
}

# ---------------------------------------------------------------------------
# Check: padrino NOT in sudo/wheel
# ---------------------------------------------------------------------------
check_sudo_access() {
    header "Privilege Check"

    if ! id "${PADRINO_USER}" &>/dev/null; then
        fail "Cannot check sudo access — user '${PADRINO_USER}' does not exist"
        return
    fi

    local in_sudo=false
    for grp in sudo wheel admin; do
        if groups "${PADRINO_USER}" 2>/dev/null | grep -q "\b${grp}\b"; then
            fail "Padrino is in '${grp}' group — MUST be removed"
            in_sudo=true
        fi
    done

    if [[ "${in_sudo}" == false ]]; then
        pass "Padrino user has NO sudo/wheel access"
    fi

    # Check if padrino can sudo at all
    if sudo -u "${PADRINO_USER}" sudo -n true 2>/dev/null; then
        fail "Padrino user CAN execute sudo — critical security risk"
    else
        pass "Padrino user CANNOT execute sudo"
    fi
}

# ---------------------------------------------------------------------------
# Check: restrictive umask
# ---------------------------------------------------------------------------
check_umask() {
    header "umask"
    local bashrc="${PADRINO_HOME}/.bashrc"

    if [[ -f "${bashrc}" ]] && grep -q 'umask 077' "${bashrc}"; then
        pass "umask 077 set in ${bashrc}"
    else
        warn "umask 077 NOT found in ${bashrc} — add: echo 'umask 077' >> ${bashrc}"
    fi
}

# ---------------------------------------------------------------------------
# Check: SSH key-only auth
# ---------------------------------------------------------------------------
check_ssh() {
    header "SSH Configuration"

    local sshd_config="/etc/ssh/sshd_config"
    if [[ ! -f "${sshd_config}" ]]; then
        warn "sshd_config not found at ${sshd_config} — SSH may not be installed"
        return
    fi

    # PasswordAuthentication
    if grep -qi '^PasswordAuthentication\s\+no' "${sshd_config}"; then
        pass "PasswordAuthentication is 'no' — key-only SSH"
    elif grep -qi '^PasswordAuthentication\s\+yes' "${sshd_config}"; then
        fail "PasswordAuthentication is 'yes' — change to 'no' for key-only SSH"
    else
        warn "PasswordAuthentication not explicitly set — default may allow passwords"
    fi

    # PermitRootLogin
    if grep -qi '^PermitRootLogin\s\+no' "${sshd_config}"; then
        pass "PermitRootLogin is 'no'"
    elif grep -qi '^PermitRootLogin\s\+yes' "${sshd_config}"; then
        fail "PermitRootLogin is 'yes' — should be 'no' or 'prohibit-password'"
    else
        warn "PermitRootLogin not explicitly set"
    fi

    # PubkeyAuthentication
    if grep -qi '^PubkeyAuthentication\s\+yes' "${sshd_config}"; then
        pass "PubkeyAuthentication is enabled"
    elif grep -qi '^PubkeyAuthentication\s\+no' "${sshd_config}"; then
        fail "PubkeyAuthentication is disabled — SSH keys won't work"
    fi
}

# ---------------------------------------------------------------------------
# Check: UFW firewall active
# ---------------------------------------------------------------------------
check_firewall() {
    header "Firewall (UFW)"

    if ! command -v ufw &>/dev/null; then
        warn "UFW not installed"
        return
    fi

    if ufw status | grep -q "^Status: active"; then
        pass "UFW is active"
    else
        fail "UFW is NOT active — run: ufw enable"
    fi

    # Check allowed rules
    if ufw status | grep -q "^22/tcp.*ALLOW"; then
        pass "SSH (22/tcp) is allowed"
    else
        warn "SSH (22/tcp) not found in UFW rules"
    fi

    echo ""
    echo "  Current UFW rules:"
    ufw status verbose 2>/dev/null | sed 's/^/    /' || true
}

# ---------------------------------------------------------------------------
# Check: no secrets in repo
# ---------------------------------------------------------------------------
check_no_secrets() {
    header "Secrets Scan"

    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd 2>/dev/null || echo '')"

    if [[ -z "${repo_root}" || ! -d "${repo_root}" ]]; then
        warn "Cannot determine repo root — skipping secrets scan"
        return
    fi

    if [[ ! -d "${repo_root}/.git" ]]; then
        warn "${repo_root} is not a git repo — skipping scan"
        return
    fi

    # Patterns to detect (basic grep — not exhaustive)
    local patterns=(
        'TELEGRAM_BOT_TOKEN=.*[A-Za-z0-9_\-]{30,}'
        'LLM_API_KEY=.*[A-Za-z0-9_\-]{20,}'
        'PADRINO_BACKUP_KEY=.*[A-Za-z0-9_\-]{16,}'
        'ghp_[A-Za-z0-9]{36}'          # GitHub PAT
        '-----BEGIN.*PRIVATE KEY-----' # Private keys
    )

    local found_secrets=0
    for pattern in "${patterns[@]}"; do
        local matches
        matches="$(grep -rnI --exclude-dir=.git --exclude-dir=.atl --exclude='*.gpg' "${pattern}" "${repo_root}" 2>/dev/null || true)"
        if [[ -n "${matches}" ]]; then
            ((found_secrets++))
            echo "  ${RED}SECRET FOUND:${NC}"
            echo "${matches}" | sed 's/^/    /'
        fi
    done

    if (( found_secrets == 0 )); then
        pass "No secrets detected in repository"
    else
        fail "${found_secrets} potential secret(s) found — remove immediately"
    fi
}

# ---------------------------------------------------------------------------
# Check: sensitive paths not accessible by padrino
# ---------------------------------------------------------------------------
check_sensitive_paths() {
    header "Sensitive Paths — Access Test"

    if ! id "${PADRINO_USER}" &>/dev/null; then
        warn "User '${PADRINO_USER}' does not exist — skipping path checks"
        return
    fi

    local sensitive=(
        "/etc/shadow"
        "/root"
    )

    local blocked=0
    for path in "${sensitive[@]}"; do
        if sudo -u "${PADRINO_USER}" test -r "${path}" 2>/dev/null; then
            fail "Padrino user CAN read ${path} — tighten permissions"
        else
            pass "Padrino user cannot read ${path}"
            ((blocked++))
        fi
    done
}

# ---------------------------------------------------------------------------
# Check: data directories exist
# ---------------------------------------------------------------------------
check_data_dirs() {
    header "Data Directories"

    local dirs=(
        "${PADRINO_DATA}"
        "${PADRINO_DATA}/memory"
        "${PADRINO_DATA}/journal"
        "${PADRINO_DATA}/inbox"
        "${PADRINO_DATA}/exports"
        "/srv/padrino/backups"
        "/srv/padrino/logs"
    )

    for dir in "${dirs[@]}"; do
        if [[ -d "${dir}" ]]; then
            pass "Directory exists: ${dir}"
        else
            warn "Directory missing: ${dir} — run setup.sh"
        fi
    done
}

# ---------------------------------------------------------------------------
# Check: .env file permissions (if it exists)
# ---------------------------------------------------------------------------
check_env_permissions() {
    header "Secrets File Permissions"

    local env_files=(
        "${PADRINO_HOME}/.hermes/.env"
        "${PADRINO_HOME}/.hermes/secrets.env"
    )

    for env_file in "${env_files[@]}"; do
        if [[ -f "${env_file}" ]]; then
            local perms
            perms="$(stat -c '%a' "${env_file}")"
            if [[ "${perms}" == "600" ]]; then
                pass "${env_file} has correct permissions (600)"
            else
                fail "${env_file} has permissions ${perms} — must be 600. Fix: chmod 600 ${env_file}"
            fi
        else
            pass "${env_file} does not exist yet (expected before go-live)"
        fi
    done
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local total=$((PASS + WARN + FAIL))
    echo ""
    echo "=============================================="
    echo "  Padrino Digital — Security Audit Summary"
    echo "=============================================="
    echo ""
    echo "  Date:       ${TIMESTAMP}"
    echo "  Total:      ${total} checks"
    echo "  Passed:     ${PASS}"
    echo "  Warnings:   ${WARN}"
    echo "  Failed:     ${FAIL}"
    echo ""

    if (( FAIL > 0 )); then
        echo "  ${RED}Verdict: FAIL${NC} — fix ${FAIL} critical issue(s) before go-live."
        echo ""
        exit 2
    elif (( WARN > 0 )); then
        echo "  ${YELLOW}Verdict: PASS WITH WARNINGS${NC} — review ${WARN} warning(s)."
        echo ""
        exit 1
    else
        echo "  ${GREEN}Verdict: ALL CLEAN${NC} — Padrino Digital is ready."
        echo ""
        exit 0
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "  Padrino Digital — Security Audit"
    echo "  Started: ${TIMESTAMP}"
    echo ""

    check_root
    check_padrino_user
    check_sudo_access
    check_umask
    check_ssh
    check_firewall
    check_no_secrets
    check_sensitive_paths
    check_data_dirs
    check_env_permissions
    print_summary
}

main "$@"
