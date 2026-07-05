#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# backup.sh — Padrino Digital encrypted backup
# ---------------------------------------------------------------------------
# Creates a compressed, checksummed, GPG-encrypted backup of all Padrino data.
# Runs daily via cron (0 3 * * *) or manually via /backup command.
#
# Usage:
#   bash backup.sh              # Full backup
#   bash backup.sh --dry-run    # Validate env and paths without creating backup
#
# Environment:
#   PADRINO_BACKUP_KEY  — GPG symmetric passphrase (REQUIRED)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly BACKUP_DATE="$(date '+%Y-%m-%d')"
readonly BACKUP_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
readonly TIMESTAMP="$(date '+%H:%M:%S')"

# Paths (relative to padrino user home)
readonly PADRINO_HOME="${HOME}"
readonly HERMES_HOME="${PADRINO_HOME}/.hermes"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_BACKUPS="/srv/padrino/backups"
readonly PADRINO_LOGS="/srv/padrino/logs"

readonly BACKUP_TMP="/tmp/padrino-backup-${BACKUP_DATE}"
readonly BACKUP_FILE="${PADRINO_BACKUPS}/${BACKUP_DATE}.tar.gz.gpg"
readonly BACKUP_CHECKSUM="${PADRINO_BACKUPS}/${BACKUP_DATE}.tar.gz.sha256"
readonly LOG_FILE="${PADRINO_LOGS}/backup.log"

# Retention (configurable via retention.conf)
readonly RETENTION_DAILY=7
readonly RETENTION_WEEKLY=4
readonly RETENTION_MONTHLY=12

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

DRY_RUN=false

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()    { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
success(){ echo -e "  ${GREEN}✓${NC} $*" | tee -a "${LOG_FILE}"; }
error()  { echo -e "  ${RED}✗${NC} $*" | tee -a "${LOG_FILE}" >&2; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $*" | tee -a "${LOG_FILE}"; }
info()   { echo -e "  ${CYAN}→${NC} $*"; }

die() {
    echo -e "${RED}ERROR [$(date '+%H:%M:%S')]:${NC} $*" | tee -a "${LOG_FILE}" >&2
    log "BACKUP FAILED: $*"
    exit 1
}

cleanup() {
    if [[ "${DRY_RUN}" != "true" ]]; then
        rm -rf "${BACKUP_TMP}" /tmp/padrino-${BACKUP_DATE}.tar.gz /tmp/padrino-${BACKUP_DATE}.tar.gz.sha256 2>/dev/null || true
    fi
}
trap cleanup EXIT

usage() {
    cat <<EOF
${BOLD}backup.sh${NC} — Padrino Digital Encrypted Backup

${BOLD}Usage:${NC}
  bash backup.sh [--dry-run]

${BOLD}Environment:${NC}
  PADRINO_BACKUP_KEY    GPG symmetric passphrase (required)

${BOLD}Output:${NC}
  Encrypted backup:  ${BACKUP_FILE}
  Checksum file:     ${BACKUP_CHECKSUM}
  Log:               ${LOG_FILE}
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) usage ;;
        *) die "Unknown option: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Step 1 — Preflight checks
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   Padrino Digital Backup — ${BACKUP_DATE}              ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"

log "Backup started: ${BACKUP_TIME}"

# Ensure log directory exists
mkdir -p "$(dirname "${LOG_FILE}")"

# Check PADRINO_BACKUP_KEY
if [[ -z "${PADRINO_BACKUP_KEY:-}" ]]; then
    die "PADRINO_BACKUP_KEY is not set. This is the GPG passphrase for backup encryption. Set it in ~/.hermes/secrets.env"
fi

# Check required tools
for tool in sqlite3 tar gpg sha256sum; do
    if ! command -v "${tool}" &>/dev/null; then
        die "${tool} is not installed. Required for backup."
    fi
done
success "Required tools available (sqlite3, tar, gpg, sha256sum)"

# Check source paths exist
for path in "${PADRINO_DATA}/padrino.db" "${HERMES_HOME}/memory" "${PROJECT_ROOT}/padrino/skills"; do
    if [[ ! -e "${path}" ]]; then
        warn "Source path not found: ${path} (will skip)"
    fi
done

# ---------------------------------------------------------------------------
# Step 2 — Check disk space
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[1/7] Disk space check${NC}"

# Estimate source size
SOURCE_SIZE_KB=$(du -sk "${PADRINO_DATA}" "${HERMES_HOME}/memory" "${PROJECT_ROOT}/padrino/skills" 2>/dev/null | awk '{sum+=$1} END {print sum}')
SOURCE_SIZE_MB=$((SOURCE_SIZE_KB / 1024))
NEEDED_MB=$((SOURCE_SIZE_MB * 3))  # Rough estimate: source + compressed + encrypted

BACKUP_DISK_FREE_KB=$(df -k "${PADRINO_BACKUPS}" 2>/dev/null | awk 'NR==2 {print $4}')
BACKUP_DISK_FREE_MB=$((BACKUP_DISK_FREE_KB / 1024))

info "Estimated source size: ${SOURCE_SIZE_MB}MB"
info "Estimated backup need: ${NEEDED_MB}MB"
info "Available space: ${BACKUP_DISK_FREE_MB}MB"

if [[ ${BACKUP_DISK_FREE_MB} -lt ${NEEDED_MB} ]]; then
    die "Insufficient disk space. Need ~${NEEDED_MB}MB, have ${BACKUP_DISK_FREE_MB}MB."
fi
success "Disk space sufficient (${BACKUP_DISK_FREE_MB}MB free)"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo ""
    success "Dry run complete — environment valid, all paths accessible."
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 3 — Create staging directory
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[2/7] Staging backup data${NC}"
rm -rf "${BACKUP_TMP}"
mkdir -p "${BACKUP_TMP}"/{data,memory,config,skills,cron,docs}

# ---------------------------------------------------------------------------
# Step 4 — Collect data
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[3/7] Collecting data sources${NC}"

# SQLite dump
if [[ -f "${PADRINO_DATA}/padrino.db" ]]; then
    info "Dumping padrino.db..."
    if sqlite3 "${PADRINO_DATA}/padrino.db" ".dump" > "${BACKUP_TMP}/data/padrino.sql" 2>/dev/null; then
        success "padrino.db dumped ($(wc -c < "${BACKUP_TMP}/data/padrino.sql") bytes)"
    else
        error "Failed to dump padrino.db"
        die "SQLite dump failed"
    fi
else
    warn "padrino.db not found — skipping"
fi

# Memory files
if [[ -d "${HERMES_HOME}/memory" ]]; then
    info "Copying memory files..."
    cp -r "${HERMES_HOME}/memory/"* "${BACKUP_TMP}/memory/" 2>/dev/null || true
    success "Memory files copied"
fi

# Config files (excluding secrets)
if [[ -d "${PROJECT_ROOT}/padrino/config" ]]; then
    info "Copying config files..."
    for f in "${PROJECT_ROOT}"/padrino/config/*.txt "${PROJECT_ROOT}"/padrino/config/*.service "${PROJECT_ROOT}"/padrino/config/*.conf; do
        [[ -f "$f" ]] && cp "$f" "${BACKUP_TMP}/config/" 2>/dev/null || true
    done
    success "Config files copied"
fi

# Skills
if [[ -d "${PROJECT_ROOT}/padrino/skills" ]]; then
    info "Copying skill files..."
    cp -r "${PROJECT_ROOT}/padrino/skills/"* "${BACKUP_TMP}/skills/" 2>/dev/null || true
    rm -f "${BACKUP_TMP}/skills/.gitkeep"
    success "Skill files copied"
fi

# Cron definitions
if [[ -d "${PROJECT_ROOT}/padrino/cron" ]]; then
    info "Copying cron jobs..."
    cp -r "${PROJECT_ROOT}/padrino/cron/"* "${BACKUP_TMP}/cron/" 2>/dev/null || true
    success "Cron jobs copied"
fi

# Reports
if [[ -d "${PROJECT_ROOT}/padrino/reports" ]]; then
    info "Copying reports..."
    cp -r "${PROJECT_ROOT}/padrino/reports/"* "${BACKUP_TMP}/reports/" 2>/dev/null || true
    success "Reports copied"
fi

# Documentation
if [[ -d "${PROJECT_ROOT}/padrino/docs" ]]; then
    info "Copying docs..."
    cp -r "${PROJECT_ROOT}/padrino/docs/"* "${BACKUP_TMP}/docs/" 2>/dev/null || true
    rm -f "${BACKUP_TMP}/docs/.gitkeep"
    success "Docs copied"
fi

# Hermes config (if exists)
if [[ -f "${HERMES_HOME}/config.yaml" ]]; then
    cp "${HERMES_HOME}/config.yaml" "${BACKUP_TMP}/hermes-config.yaml" 2>/dev/null || true
    success "Hermes config copied"
fi

# ---------------------------------------------------------------------------
# Step 5 — Verify no secrets leaked
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[4/7] Secrets leak check${NC}"

if grep -rI "HERMES_TELEGRAM_TOKEN\|PADRINO_BACKUP_KEY\|GIT_READONLY_TOKEN\|API_KEY.*[A-Za-z0-9]\{20,\}" "${BACKUP_TMP}/" 2>/dev/null; then
    die "CRITICAL: Secret pattern found in backup staging area. Backup aborted to prevent secret leakage."
fi
success "No secrets found in backup staging"

# ---------------------------------------------------------------------------
# Step 6 — Compress, checksum, encrypt
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[5/7] Compress + checksum + encrypt${NC}"

# Ensure backup directory exists
mkdir -p "${PADRINO_BACKUPS}"

# Compress
info "Compressing..."
if tar czf "/tmp/padrino-${BACKUP_DATE}.tar.gz" -C "${BACKUP_TMP}" . 2>/dev/null; then
    COMPRESSED_SIZE=$(stat -c%s "/tmp/padrino-${BACKUP_DATE}.tar.gz" 2>/dev/null || stat -f%z "/tmp/padrino-${BACKUP_DATE}.tar.gz" 2>/dev/null)
    success "Compressed: $((COMPRESSED_SIZE / 1024 / 1024))MB"
else
    die "Compression failed"
fi

# Checksum
info "Computing SHA-256..."
sha256sum "/tmp/padrino-${BACKUP_DATE}.tar.gz" > "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256"
CHECKSUM_FULL=$(cut -d' ' -f1 "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256")
success "SHA-256: ${CHECKSUM_FULL:0:16}..."

# Encrypt
info "Encrypting with GPG AES-256..."
if gpg --symmetric --batch --passphrase "${PADRINO_BACKUP_KEY}" \
       --cipher-algo AES256 \
       --compress-algo none \
       -o "${BACKUP_FILE}" \
       "/tmp/padrino-${BACKUP_DATE}.tar.gz" 2>/dev/null; then
    ENCRYPTED_SIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null)
    success "Encrypted: $((ENCRYPTED_SIZE / 1024 / 1024))MB"
else
    die "GPG encryption failed"
fi

# Store checksum
cp "/tmp/padrino-${BACKUP_DATE}.tar.gz.sha256" "${BACKUP_CHECKSUM}"
success "Checksum saved"

# ---------------------------------------------------------------------------
# Step 7 — Rotate old backups
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[6/7] Rotating old backups${NC}"

DELETED_COUNT=0

# Delete daily backups older than RETENTION_DAILY days
while IFS= read -r -d '' old_backup; do
    info "Removing old backup: $(basename "${old_backup}")"
    rm -f "${old_backup}" "${old_backup%.gpg}.sha256"
    ((DELETED_COUNT++)) || true
done < <(find "${PADRINO_BACKUPS}" -name "*.tar.gz.gpg" -mtime +${RETENTION_DAILY} -print0 2>/dev/null || true)

if [[ ${DELETED_COUNT} -gt 0 ]]; then
    success "Rotated ${DELETED_COUNT} old backup(s)"
else
    success "No backups to rotate (within ${RETENTION_DAILY}-day retention)"
fi

# ---------------------------------------------------------------------------
# Step 8 — Size anomaly check
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[7/7] Anomaly check${NC}"

# Calculate 7-day average from existing backup files
BACKUP_COUNT=$(find "${PADRINO_BACKUPS}" -name "*.tar.gz.gpg" -mtime -7 2>/dev/null | wc -l)
if [[ ${BACKUP_COUNT} -ge 2 ]]; then
    TOTAL_SIZE=0
    while IFS= read -r -d '' backup_f; do
        size=$(stat -c%s "${backup_f}" 2>/dev/null || stat -f%z "${backup_f}" 2>/dev/null)
        TOTAL_SIZE=$((TOTAL_SIZE + size))
    done < <(find "${PADRINO_BACKUPS}" -name "*.tar.gz.gpg" -mtime -7 -print0 2>/dev/null)
    
    AVG_SIZE=$((TOTAL_SIZE / BACKUP_COUNT))
    AVG_MB=$((AVG_SIZE / 1024 / 1024))
    CURR_MB=$((ENCRYPTED_SIZE / 1024 / 1024))
    
    if [[ ${ENCRYPTED_SIZE} -lt $((AVG_SIZE / 2)) ]]; then
        warn "SIZE ANOMALY: ${CURR_MB}MB (7-day avg: ${AVG_MB}MB)"
        warn "Today's backup is less than 50% of average. Something might be missing."
    elif [[ ${ENCRYPTED_SIZE} -gt $((AVG_SIZE * 2)) ]]; then
        warn "SIZE ANOMALY: ${CURR_MB}MB (7-day avg: ${AVG_MB}MB)"
        warn "Today's backup is more than 200% of average. Verify contents."
    else
        success "Size within normal range (${CURR_MB}MB vs ${AVG_MB}MB avg)"
    fi
else
    success "Not enough history for anomaly detection (need 2+ backups in 7 days)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Backup complete — ${BACKUP_DATE}${NC}"
echo -e "${BOLD}${GREEN}  File:    ${BACKUP_FILE}${NC}"
echo -e "${BOLD}${GREEN}  Size:    $((ENCRYPTED_SIZE / 1024 / 1024))MB${NC}"
echo -e "${BOLD}${GREEN}  SHA-256: ${CHECKSUM_FULL:0:16}...${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"

log "BACKUP COMPLETED: ${BACKUP_DATE} — Size: $((ENCRYPTED_SIZE / 1024 / 1024))MB — SHA256: ${CHECKSUM_FULL:0:16}"

exit 0
