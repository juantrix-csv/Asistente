#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# restore.sh — Padrino Digital backup restore
# ---------------------------------------------------------------------------
# Restores Padrino data from an encrypted backup. Verifies checksum,
# decrypts, extracts, and validates database integrity.
#
# Usage:
#   bash restore.sh YYYY-MM-DD              # Restore from specified date
#   bash restore.sh --list                   # List available backups
#   bash restore.sh --latest                 # Restore from most recent backup
#
# Environment:
#   PADRINO_BACKUP_KEY  — GPG symmetric passphrase (REQUIRED)
#
# WARNING: This OVERWRITES current data. User confirmation is required.
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

readonly PADRINO_HOME="${HOME}"
readonly HERMES_HOME="${PADRINO_HOME}/.hermes"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_BACKUPS="/srv/padrino/backups"
readonly PADRINO_LOGS="/srv/padrino/logs"
readonly LOG_FILE="${PADRINO_LOGS}/restore.log"

readonly RESTORE_TMP="/tmp/padrino-restore"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

RESTORE_DATE=""
LIST_MODE=false
LATEST_MODE=false

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()    { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
success(){ echo -e "  ${GREEN}✓${NC} $*"; }
error()  { echo -e "  ${RED}✗${NC} $*" >&2; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $*"; }
info()   { echo -e "  ${CYAN}→${NC} $*"; }

die() {
    echo -e "${RED}ERROR:${NC} $*" | tee -a "${LOG_FILE}" >&2
    log "RESTORE FAILED: $*"
    exit 1
}

cleanup() {
    rm -rf "${RESTORE_TMP}" /tmp/restore-decrypted.tar.gz 2>/dev/null || true
}
trap cleanup EXIT

usage() {
    cat <<EOF
${BOLD}restore.sh${NC} — Padrino Digital Backup Restore

${BOLD}Usage:${NC}
  bash restore.sh YYYY-MM-DD       Restore from specified date
  bash restore.sh --latest          Restore from most recent backup
  bash restore.sh --list            List available backups

${BOLD}Environment:${NC}
  PADRINO_BACKUP_KEY    GPG symmetric passphrase (required)

${BOLD}WARNING:${NC} Restoring OVERWRITES current data. Confirmation is always required.
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --list) LIST_MODE=true; shift ;;
        --latest) LATEST_MODE=true; shift ;;
        --help|-h) usage ;;
        -*)
            die "Unknown option: $1. Use --help for usage."
            ;;
        *)
            if [[ -z "${RESTORE_DATE}" ]]; then
                RESTORE_DATE="$1"
            else
                die "Unexpected extra argument: $1"
            fi
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# List mode
# ---------------------------------------------------------------------------
if [[ "${LIST_MODE}" == "true" ]]; then
    echo -e "\n${BOLD}Available Backups${NC}"
    echo "─────────────────────────────────────"
    
    if [[ ! -d "${PADRINO_BACKUPS}" ]]; then
        echo "  No backups directory found."
        exit 0
    fi
    
    BACKUPS_FOUND=0
    for f in "${PADRINO_BACKUPS}"/*.tar.gz.gpg; do
        [[ -f "$f" ]] || continue
        BACKUPS_FOUND=1
        filename=$(basename "$f")
        date_part="${filename%%.tar.gz.gpg}"
        size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null)
        size_mb=$((size / 1024 / 1024))
        echo "  ${date_part}  —  ${size_mb}MB"
    done
    
    if [[ ${BACKUPS_FOUND} -eq 0 ]]; then
        echo "  No backups found."
    fi
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# Resolve restore date
# ---------------------------------------------------------------------------
if [[ "${LATEST_MODE}" == "true" ]]; then
    RESTORE_DATE=$(ls -1t "${PADRINO_BACKUPS}"/*.tar.gz.gpg 2>/dev/null | head -1 | sed 's/.*\///;s/\.tar\.gz\.gpg//')
    if [[ -z "${RESTORE_DATE}" ]]; then
        die "No backups found in ${PADRINO_BACKUPS}"
    fi
    info "Latest backup: ${RESTORE_DATE}"
fi

if [[ -z "${RESTORE_DATE}" ]]; then
    die "No restore date specified. Use YYYY-MM-DD, --latest, or --list."
fi

# Validate date format
if [[ ! "${RESTORE_DATE}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    die "Invalid date format: ${RESTORE_DATE}. Use YYYY-MM-DD."
fi

readonly BACKUP_FILE="${PADRINO_BACKUPS}/${RESTORE_DATE}.tar.gz.gpg"
readonly CHECKSUM_FILE="${PADRINO_BACKUPS}/${RESTORE_DATE}.tar.gz.sha256"

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
mkdir -p "$(dirname "${LOG_FILE}")"
log "Restore initiated for: ${RESTORE_DATE}"

if [[ -z "${PADRINO_BACKUP_KEY:-}" ]]; then
    die "PADRINO_BACKUP_KEY is not set."
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
    die "Backup not found: ${BACKUP_FILE}"
fi

for tool in gpg tar sha256sum sqlite3; do
    if ! command -v "${tool}" &>/dev/null; then
        die "${tool} is not installed."
    fi
done

# ---------------------------------------------------------------------------
# Step 1 — Verify checksum
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[1/5] Checksum verification${NC}"

# Decrypt to temp file for checksum verification
info "Decrypting backup for verification..."
if ! gpg --decrypt --batch --passphrase "${PADRINO_BACKUP_KEY}" \
        -o "/tmp/restore-decrypted.tar.gz" \
        "${BACKUP_FILE}" 2>/dev/null; then
    die "Decryption failed. Check PADRINO_BACKUP_KEY."
fi
success "Decrypted successfully"

# Verify checksum
if [[ -f "${CHECKSUM_FILE}" ]]; then
    info "Verifying SHA-256 checksum..."
    EXPECTED=$(cut -d' ' -f1 "${CHECKSUM_FILE}")
    ACTUAL=$(sha256sum "/tmp/restore-decrypted.tar.gz" | cut -d' ' -f1)
    
    if [[ "${EXPECTED}" == "${ACTUAL}" ]]; then
        success "Checksum verified: ${ACTUAL:0:16}..."
    else
        rm -f "/tmp/restore-decrypted.tar.gz"
        die "Checksum MISMATCH! Expected ${EXPECTED:0:16}..., got ${ACTUAL:0:16}... Backup may be corrupt. Restore ABORTED."
    fi
else
    warn "No checksum file found for ${RESTORE_DATE} — skipping verification"
fi

# ---------------------------------------------------------------------------
# Step 2 — User confirmation
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[2/5] Confirmation${NC}"
echo ""
echo -e "  ${YELLOW}${BOLD}⚠️  ATENCIÓN: Restauración de Backup${NC}"
echo ""
echo "  Esto va a SOBRESCRIBIR los siguientes datos:"
echo "    • Base de datos SQLite  (/srv/padrino/data/padrino.db)"
echo "    • Archivos de memoria   (~/.hermes/memory/)"
echo "    • Configuraciones       (padrino/config/)"
echo "    • Skills                (~/.hermes/skills/)"
echo "    • Cron jobs             (padrino/cron/)"
echo ""
echo "  Los datos actuales serán reemplazados por los del backup:"
echo -e "  ${BOLD}${RESTORE_DATE}${NC}"
echo ""

# In automated mode (cron), abort here — restore requires interactive confirmation
if [[ ! -t 0 ]]; then
    error "Restore requires interactive confirmation. Not running in interactive terminal."
    die "Cannot confirm restore in non-interactive mode."
fi

read -r -p "  ¿Confirmás la restauración? (escribí 'SI-RESTAURAR' para confirmar): " CONFIRMATION
echo ""

if [[ "${CONFIRMATION}" != "SI-RESTAURAR" ]]; then
    warn "Restore CANCELLED by user."
    log "RESTORE CANCELLED: user did not confirm."
    exit 0
fi

success "Confirmation received"

# ---------------------------------------------------------------------------
# Step 3 — Extract
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[3/5] Extracting backup${NC}"

rm -rf "${RESTORE_TMP}"
mkdir -p "${RESTORE_TMP}"

info "Extracting files..."
if tar xzf "/tmp/restore-decrypted.tar.gz" -C "${RESTORE_TMP}"; then
    success "Extracted to ${RESTORE_TMP}"
else
    die "Extraction failed. Backup archive may be corrupt."
fi

# List what we're about to restore
echo ""
info "Contents to restore:"
find "${RESTORE_TMP}" -type f | sort | while IFS= read -r f; do
    echo "    ${f#${RESTORE_TMP}/}"
done

# ---------------------------------------------------------------------------
# Step 4 — Restore data
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[4/5] Restoring data${NC}"

# Back up current database before overwriting (just in case)
if [[ -f "${PADRINO_DATA}/padrino.db" ]]; then
    info "Backing up current database..."
    cp "${PADRINO_DATA}/padrino.db" "${PADRINO_DATA}/padrino.db.pre-restore-${RESTORE_DATE}" 2>/dev/null || true
    success "Current DB saved as padrino.db.pre-restore-${RESTORE_DATE}"
fi

# Restore SQLite database
if [[ -f "${RESTORE_TMP}/data/padrino.sql" ]]; then
    info "Restoring padrino.db..."
    if sqlite3 "${PADRINO_DATA}/padrino.db" < "${RESTORE_TMP}/data/padrino.sql" 2>/dev/null; then
        success "padrino.db restored"
    else
        # Attempt recovery: restore from pre-restore backup
        if [[ -f "${PADRINO_DATA}/padrino.db.pre-restore-${RESTORE_DATE}" ]]; then
            mv "${PADRINO_DATA}/padrino.db.pre-restore-${RESTORE_DATE}" "${PADRINO_DATA}/padrino.db"
            die "SQLite restore failed. Original database has been restored from pre-restore backup."
        else
            die "SQLite restore failed and no pre-restore backup available."
        fi
    fi
else
    warn "No padrino.sql in backup — skipping database restore"
fi

# Restore memory files
if [[ -d "${RESTORE_TMP}/memory" ]] && [[ "$(ls -A "${RESTORE_TMP}/memory" 2>/dev/null)" ]]; then
    info "Restoring memory files..."
    mkdir -p "${HERMES_HOME}/memory"
    rsync -a --delete "${RESTORE_TMP}/memory/" "${HERMES_HOME}/memory/" 2>/dev/null || \
        cp -r "${RESTORE_TMP}/memory/"* "${HERMES_HOME}/memory/" 2>/dev/null || true
    success "Memory files restored"
fi

# Restore configs
if [[ -d "${RESTORE_TMP}/config" ]] && [[ "$(ls -A "${RESTORE_TMP}/config" 2>/dev/null)" ]]; then
    info "Restoring config files..."
    cp "${RESTORE_TMP}/config/"* "${PROJECT_ROOT}/padrino/config/" 2>/dev/null || true
    success "Config files restored"
fi

# Restore skills
if [[ -d "${RESTORE_TMP}/skills" ]] && [[ "$(ls -A "${RESTORE_TMP}/skills" 2>/dev/null)" ]]; then
    info "Restoring skill files..."
    rsync -a --delete "${RESTORE_TMP}/skills/" "${HERMES_HOME}/skills/" 2>/dev/null || \
        cp -r "${RESTORE_TMP}/skills/"* "${HERMES_HOME}/skills/" 2>/dev/null || true
    success "Skill files restored"
fi

# Restore cron
if [[ -d "${RESTORE_TMP}/cron" ]] && [[ "$(ls -A "${RESTORE_TMP}/cron" 2>/dev/null)" ]]; then
    info "Restoring cron jobs..."
    cp "${RESTORE_TMP}/cron/"* "${PROJECT_ROOT}/padrino/cron/" 2>/dev/null || true
    success "Cron jobs restored"
fi

# Restore hermes config
if [[ -f "${RESTORE_TMP}/hermes-config.yaml" ]]; then
    info "Restoring Hermes config..."
    cp "${RESTORE_TMP}/hermes-config.yaml" "${HERMES_HOME}/config.yaml"
    success "Hermes config restored"
fi

# Done restoring — remove pre-restore backup
rm -f "${PADRINO_DATA}/padrino.db.pre-restore-${RESTORE_DATE}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Step 5 — Verify integrity
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[5/5] Integrity verification${NC}"

info "Running PRAGMA integrity_check..."
INTEGRITY=$(sqlite3 "${PADRINO_DATA}/padrino.db" "PRAGMA integrity_check;" 2>&1)

if [[ "${INTEGRITY}" == "ok" ]]; then
    success "Database integrity: OK"
else
    error "Database integrity check FAILED: ${INTEGRITY}"
    die "Restored database failed integrity check. Manual recovery required."
fi

# Verify memory directory exists and is writable
if [[ -d "${HERMES_HOME}/memory" ]] && [[ -w "${HERMES_HOME}/memory" ]]; then
    success "Memory directory accessible"
else
    warn "Memory directory not accessible — may need permissions fix"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Restauración completa${NC}"
echo -e "${BOLD}${GREEN}  Backup:  ${RESTORE_DATE}${NC}"
echo -e "${BOLD}${GREEN}  DB:      Integridad verificada ✓${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"

log "RESTORE COMPLETED: ${RESTORE_DATE} — Integrity: ${INTEGRITY}"

exit 0
