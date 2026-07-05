#!/usr/bin/env bash
# =============================================================================
# Padrino Digital — Database Migration Runner
# =============================================================================
# Applies versioned SQL migrations from padrino/sql/ to padrino.db.
#
# Usage:
#   ./migrate.sh                    # Apply all pending migrations
#   ./migrate.sh --dry-run          # Show pending migrations without applying
#   ./migrate.sh --status           # Show current schema version
#   ./migrate.sh --backup           # Backup DB before migrating (recommended)
#
# Environment:
#   PADRINO_DB_PATH   — path to padrino.db (default: /srv/padrino/data/padrino.db)
#   PADRINO_SQL_DIR   — path to migration files (default: ../sql/)
#   PADRINO_BACKUP_DIR — path for backups (default: /srv/padrino/data/backups/)
# =============================================================================

set -euo pipefail

# --- Configuration ---
DB_PATH="${PADRINO_DB_PATH:-/srv/padrino/data/padrino.db}"
SQL_DIR="${PADRINO_SQL_DIR:-$(dirname "$0")/../sql}"
BACKUP_DIR="${PADRINO_BACKUP_DIR:-/srv/padrino/data/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DRY_RUN=false
SHOW_STATUS=false
DO_BACKUP=false

# --- Color output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# --- Parse arguments ---
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --status)  SHOW_STATUS=true ;;
        --backup)  DO_BACKUP=true ;;
        *)
            log_error "Unknown argument: $arg"
            echo "Usage: $0 [--dry-run] [--status] [--backup]"
            exit 1
            ;;
    esac
done

# --- Pre-flight checks ---

# Check sqlite3 is available
if ! command -v sqlite3 &>/dev/null; then
    log_error "sqlite3 not found. Install with: apt-get install sqlite3"
    exit 1
fi

# Check SQL directory exists
if [ ! -d "$SQL_DIR" ]; then
    log_error "SQL directory not found: $SQL_DIR"
    exit 1
fi

# --- Status check ---
if $SHOW_STATUS; then
    if [ -f "$DB_PATH" ]; then
        VERSION=$(sqlite3 "$DB_PATH" "SELECT COALESCE(MAX(version), 0) FROM schema_version;" 2>/dev/null || echo "0")
        echo "Database: $DB_PATH"
        echo "Schema version: $VERSION"
    else
        echo "Database does not exist yet: $DB_PATH"
        echo "Schema version: 0 (not initialized)"
    fi
    exit 0
fi

# --- Backup ---
if $DO_BACKUP; then
    if [ -f "$DB_PATH" ]; then
        mkdir -p "$BACKUP_DIR"
        BACKUP_FILE="$BACKUP_DIR/padrino_pre_migrate_${TIMESTAMP}.db"
        log_info "Backing up database to $BACKUP_FILE"
        cp "$DB_PATH" "$BACKUP_FILE"
        log_ok "Backup complete: $(du -h "$BACKUP_FILE" | cut -f1)"
    else
        log_warn "No existing database to backup"
    fi
fi

# --- Determine current version ---
if [ -f "$DB_PATH" ]; then
    CURRENT_VERSION=$(sqlite3 "$DB_PATH" "SELECT COALESCE(MAX(version), 0) FROM schema_version;" 2>/dev/null || echo "0")
    log_info "Current schema version: $CURRENT_VERSION"
else
    CURRENT_VERSION=0
    log_info "Database does not exist. Will create at: $DB_PATH"
    # Create parent directory
    mkdir -p "$(dirname "$DB_PATH")"
fi

# --- Find pending migrations ---
PENDING_MIGRATIONS=()
for migration in "$SQL_DIR"/*_*.sql; do
    [ -e "$migration" ] || continue
    BASENAME=$(basename "$migration")
    MIGRATION_VERSION=$(echo "$BASENAME" | grep -oP '^\d+')
    if [ -z "$MIGRATION_VERSION" ]; then
        log_warn "Skipping file without version prefix: $BASENAME"
        continue
    fi
    MIGRATION_VERSION=$((10#$MIGRATION_VERSION))  # Convert to decimal (strip leading zeros)
    if [ "$MIGRATION_VERSION" -gt "$CURRENT_VERSION" ]; then
        PENDING_MIGRATIONS+=("$migration")
    fi
done

# --- Dry run ---
if $DRY_RUN; then
    if [ ${#PENDING_MIGRATIONS[@]} -eq 0 ]; then
        echo "No pending migrations."
    else
        echo "Pending migrations (${#PENDING_MIGRATIONS[@]}):"
        for m in "${PENDING_MIGRATIONS[@]}"; do
            echo "  - $(basename "$m")"
        done
    fi
    exit 0
fi

# --- Apply migrations ---
if [ ${#PENDING_MIGRATIONS[@]} -eq 0 ]; then
    log_ok "Database is up to date (version $CURRENT_VERSION)"
    exit 0
fi

log_info "Applying ${#PENDING_MIGRATIONS[@]} migration(s)..."

APPLIED=0
FAILED=0

for migration in "${PENDING_MIGRATIONS[@]}"; do
    BASENAME=$(basename "$migration")
    log_info "Running: $BASENAME"

    if sqlite3 "$DB_PATH" < "$migration" 2>&1; then
        APPLIED=$((APPLIED + 1))
        log_ok "Applied: $BASENAME"
    else
        FAILED=$((FAILED + 1))
        log_error "FAILED: $BASENAME"
        log_error "Migration stopped. Database may be in inconsistent state."
        log_error "Restore from backup if needed: cp $BACKUP_DIR/padrino_pre_migrate_${TIMESTAMP}.db $DB_PATH"
        exit 1
    fi
done

# --- Report ---
NEW_VERSION=$(sqlite3 "$DB_PATH" "SELECT MAX(version) FROM schema_version;" 2>/dev/null)

echo ""
echo "=========================================="
echo "  Migration Summary"
echo "=========================================="
echo "  Applied:  $APPLIED"
echo "  Failed:   $FAILED"
echo "  Version:  $CURRENT_VERSION → $NEW_VERSION"
echo "  Database: $DB_PATH"
echo "=========================================="

if $DO_BACKUP; then
    echo ""
    echo "Pre-migration backup: $BACKUP_DIR/padrino_pre_migrate_${TIMESTAMP}.db"
fi

log_ok "Migration complete."
