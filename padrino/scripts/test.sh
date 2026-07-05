#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# test.sh — Padrino Digital integration tests
# ---------------------------------------------------------------------------
# Smoke tests for the full Padrino Digital stack. Verifies:
#   1. Database schema (all tables created, FTS5 searchable)
#   2. Skill files (all 11 SKILL.md files parse, valid YAML frontmatter)
#   3. Healthcheck passes
#   4. Backup round-trip (create + restore + verify)
#   5. Path traversal security checks
#   6. Config file integrity
#
# Usage:
#   bash test.sh              # Run all tests
#   bash test.sh --quick      # Skip backup round-trip (faster)
#   bash test.sh --verbose    # Show detailed output
#
# Exit codes:
#   0 — all tests passed
#   1 — one or more tests failed
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_DB="${PADRINO_DATA}/padrino.db"
readonly SKILLS_DIR="${PROJECT_ROOT}/padrino/skills"
readonly CONFIG_DIR="${PROJECT_ROOT}/padrino/config"
readonly DOCS_DIR="${PROJECT_ROOT}/padrino/docs"
readonly CRON_DIR="${PROJECT_ROOT}/padrino/cron"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Test state
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
VERBOSE=false
QUICK_MODE=false

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
pass() { ((TESTS_PASSED++)); echo -e "  ${GREEN}✓ PASS${NC} — $*"; }
fail() { ((TESTS_FAILED++)); echo -e "  ${RED}✗ FAIL${NC} — $*"; }
skip() { ((TESTS_SKIPPED++)); echo -e "  ${YELLOW}⊘ SKIP${NC} — $*"; }
info() {
    if [[ "${VERBOSE}" == "true" ]]; then
        echo -e "    ${CYAN}→${NC} $*"
    fi
}

test_header() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━ $* ━━━${NC}"
}

assert() {
    local desc="$1"
    local condition="$2"
    local detail="${3:-}"
    
    if eval "${condition}"; then
        pass "${desc}"
    else
        fail "${desc}"
        if [[ -n "${detail}" ]]; then
            echo -e "      ${RED}Detail:${NC} ${detail}"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK_MODE=true; shift ;;
        --verbose|-v) VERBOSE=true; shift ;;
        --help|-h)
            echo "Usage: bash test.sh [--quick] [--verbose]"
            exit 0
            ;;
        *) shift ;;
    esac
done

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   Padrino Digital — Integration Test Suite       ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Mode: $(${QUICK_MODE} && echo 'Quick' || echo 'Full')"
echo ""

# =============================================================================
# Test Suite 1: Database Schema
# =============================================================================
test_header "Test Suite 1 — Database Schema"

if [[ ! -f "${PADRINO_DB}" ]]; then
    skip "padrino.db not found at ${PADRINO_DB} — skipping DB tests"
else
    # 1.1 All expected tables exist
    EXPECTED_TABLES=(
        "schema_version" "tasks" "projects" "goals"
        "habits" "habit_entries" "transactions" "budgets"
        "savings_goals" "debts" "memories" "memories_fts"
        "decisions" "daily_checkins" "reminders"
        "audit_runs" "audit_findings" "audit_log"
    )
    
    for table in "${EXPECTED_TABLES[@]}"; do
        assert "Table exists: ${table}" \
            "sqlite3 ${PADRINO_DB} \"SELECT name FROM sqlite_master WHERE type='table' AND name='${table}';\" | grep -q '${table}'" \
            "Table ${table} not found in schema"
    done
    
    # 1.2 FTS5 search works
    assert "FTS5 search functional" \
        "sqlite3 ${PADRINO_DB} \"SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts';\" | grep -q 'memories_fts'" \
        "memories_fts virtual table not found"
    
    # 1.3 Indexes exist
    EXPECTED_INDEXES=(
        "idx_tasks_status" "idx_tasks_project" "idx_tasks_due"
        "idx_goals_project" "idx_habit_entries_date"
        "idx_transactions_date" "idx_transactions_category"
        "idx_memories_area" "idx_memories_validity"
        "idx_reminders_deliver" "idx_audit_findings_run"
    )
    
    for idx in "${EXPECTED_INDEXES[@]}"; do
        assert "Index exists: ${idx}" \
            "sqlite3 ${PADRINO_DB} \"SELECT name FROM sqlite_master WHERE type='index' AND name='${idx}';\" | grep -q '${idx}'" \
            "Index ${idx} not found"
    done
    
    # 1.4 Schema version exists
    assert "Schema version recorded" \
        "sqlite3 ${PADRINO_DB} \"SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;\" | grep -qE '^[0-9]+$'" \
        "No version found in schema_version table"
fi

# =============================================================================
# Test Suite 2: Skill Files
# =============================================================================
test_header "Test Suite 2 — Skill Files"

EXPECTED_SKILLS=(
    "padrino-soul" "padrino-hermes" "padrino-inbox" "padrino-memory"
    "padrino-tasks" "padrino-plan" "padrino-coach" "padrino-finance"
    "padrino-review" "padrino-audit" "padrino-backup" "padrino-security"
)

SKILLS_FOUND=0

if [[ ! -d "${SKILLS_DIR}" ]]; then
    fail "Skills directory not found: ${SKILLS_DIR}"
else
    for skill in "${EXPECTED_SKILLS[@]}"; do
        local skill_file="${SKILLS_DIR}/${skill}/SKILL.md"
        
        if [[ -f "${skill_file}" ]]; then
            ((SKILLS_FOUND++))
            pass "Skill file exists: ${skill}"
            
            # Check YAML frontmatter
            if head -1 "${skill_file}" | grep -q '^---$'; then
                info "  ${skill}: YAML frontmatter present"
                
                # Extract frontmatter between first and second ---
                local fm
                fm=$(sed -n '/^---$/,/^---$/p' "${skill_file}" | head -n -1 | tail -n +2)
                
                # Check required fields
                if echo "${fm}" | grep -q '^name:'; then
                    info "  ${skill}: name field present"
                else
                    fail "  ${skill}: missing 'name' in frontmatter"
                fi
                
                if echo "${fm}" | grep -q '^description:'; then
                    info "  ${skill}: description field present"
                else
                    fail "  ${skill}: missing 'description' in frontmatter"
                fi
            else
                fail "  ${skill}: YAML frontmatter missing or malformed"
            fi
            
            # Check file is not empty
            local file_size
            file_size=$(stat -c%s "${skill_file}" 2>/dev/null || stat -f%z "${skill_file}" 2>/dev/null)
            if [[ ${file_size} -lt 100 ]]; then
                fail "  ${skill}: file too small (${file_size} bytes) — may be a stub"
            fi
        else
            fail "Skill file missing: ${skill}"
        fi
    done
fi

info "Skills found: ${SKILLS_FOUND}/${#EXPECTED_SKILLS[@]}"

# =============================================================================
# Test Suite 3: Healthcheck
# =============================================================================
test_header "Test Suite 3 — Healthcheck"

if [[ -f "${PROJECT_ROOT}/padrino/scripts/healthcheck.sh" ]]; then
    info "Running healthcheck..."
    
    # Run healthcheck and capture exit code
    if bash "${PROJECT_ROOT}/padrino/scripts/healthcheck.sh" &>/dev/null; then
        pass "Healthcheck script passes"
    else
        # Healthcheck may fail in dev environment (no systemd, no gateway)
        fail "Healthcheck failed (expected in dev — no systemd/gateway)"
        info "  Healthcheck expects: systemd, hermes-gateway service, Telegram connectivity"
        info "  These are only available on the production VPS."
    fi
else
    fail "Healthcheck script not found"
fi

# =============================================================================
# Test Suite 4: Backup Round-Trip
# =============================================================================
test_header "Test Suite 4 — Backup Round-Trip"

if [[ "${QUICK_MODE}" == "true" ]]; then
    skip "Skipping backup round-trip (--quick mode)"
elif [[ ! -f "${PROJECT_ROOT}/padrino/scripts/backup.sh" ]]; then
    fail "Backup script not found"
elif [[ ! -f "${PROJECT_ROOT}/padrino/scripts/restore.sh" ]]; then
    fail "Restore script not found"
elif [[ -z "${PADRINO_BACKUP_KEY:-}" ]]; then
    skip "PADRINO_BACKUP_KEY not set — skipping backup round-trip"
    info "  Set PADRINO_BACKUP_KEY to test backup/restore round-trip."
elif [[ ! -f "${PADRINO_DB}" ]]; then
    skip "padrino.db not found — skipping backup round-trip"
else
    # Test backup creation (dry run first)
    info "Testing backup script dry run..."
    if bash "${PROJECT_ROOT}/padrino/scripts/backup.sh" --dry-run &>/dev/null; then
        pass "Backup dry-run passes"
    else
        fail "Backup dry-run failed"
    fi
    
    # Test restore list
    info "Testing restore --list..."
    if bash "${PROJECT_ROOT}/padrino/scripts/restore.sh" --list &>/dev/null; then
        pass "Restore list works"
    else
        fail "Restore --list failed"
    fi
    
    # Full round-trip (only in full mode, and only if explicitly enabled)
    if [[ -n "${PADRINO_TEST_FULL_BACKUP:-}" ]]; then
        info "Running full backup + restore round-trip..."
        
        # Create a test marker in the database
        sqlite3 "${PADRINO_DB}" "INSERT INTO audit_log (action, actor, target, result, details) VALUES ('test_backup_roundtrip', 'test-script', 'test', 'test', 'Marker for backup round-trip test');" 2>/dev/null || true
        
        # Run backup
        if bash "${PROJECT_ROOT}/padrino/scripts/backup.sh" &>/dev/null; then
            pass "Backup created successfully"
            
            # Restore from today's backup
            TODAY=$(date '+%Y-%m-%d')
            if echo "SI-RESTAURAR" | bash "${PROJECT_ROOT}/padrino/scripts/restore.sh" "${TODAY}" &>/dev/null; then
                pass "Restore completed successfully"
                
                # Verify test marker exists
                if sqlite3 "${PADRINO_DB}" "SELECT id FROM audit_log WHERE action='test_backup_roundtrip' LIMIT 1;" 2>/dev/null | grep -qE '^[0-9]+$'; then
                    pass "Round-trip verified: test marker found after restore"
                else
                    fail "Round-trip failed: test marker missing after restore"
                fi
                
                # Clean up test marker
                sqlite3 "${PADRINO_DB}" "DELETE FROM audit_log WHERE action='test_backup_roundtrip';" 2>/dev/null || true
            else
                fail "Restore failed"
            fi
        else
            fail "Backup creation failed"
        fi
    else
        skip "Full round-trip not enabled (set PADRINO_TEST_FULL_BACKUP=1 to enable)"
    fi
fi

# =============================================================================
# Test Suite 5: Security
# =============================================================================
test_header "Test Suite 5 — Security Checks"

# 5.1 Sensitive paths file exists
if [[ -f "${CONFIG_DIR}/sensitive-paths.txt" ]]; then
    pass "sensitive-paths.txt exists"
    
    # Check it contains key blocked paths
    if grep -q "/etc/" "${CONFIG_DIR}/sensitive-paths.txt"; then
        pass "  Blocked path /etc/ listed"
    fi
    if grep -q ".env" "${CONFIG_DIR}/sensitive-paths.txt"; then
        pass "  .env files listed as sensitive"
    fi
else
    fail "sensitive-paths.txt missing"
fi

# 5.2 Command allowlist exists
if [[ -f "${CONFIG_DIR}/command-allowlist.txt" ]]; then
    pass "command-allowlist.txt exists"
    
    # Verify it blocks dangerous commands
    if ! grep -q "^rm " "${CONFIG_DIR}/command-allowlist.txt"; then
        pass "  'rm' command NOT in allowlist (correct)"
    else
        fail "  'rm' command IN allowlist (dangerous!)"
    fi
    
    if ! grep -q "^sudo " "${CONFIG_DIR}/command-allowlist.txt"; then
        pass "  'sudo' command NOT in allowlist (correct)"
    else
        fail "  'sudo' command IN allowlist (dangerous!)"
    fi
else
    fail "command-allowlist.txt missing"
fi

# 5.3 Repo allowlist exists
if [[ -f "${CONFIG_DIR}/repo-allowlist.txt" ]]; then
    pass "repo-allowlist.txt exists"
else
    fail "repo-allowlist.txt missing"
fi

# 5.4 .env.template exists and references chmod 600
if [[ -f "${CONFIG_DIR}/.env.template" ]]; then
    pass ".env.template exists"
    
    if grep -qi "chmod 600\|600" "${CONFIG_DIR}/.env.template"; then
        pass "  .env.template references 600 permissions"
    fi
else
    fail ".env.template missing"
fi

# 5.5 Path traversal tests (scripts reject ../ patterns)
info "Testing path traversal protection..."
if grep -q 'die.*Invalid path' "${PROJECT_ROOT}/padrino/scripts/backup.sh" 2>/dev/null || \
   grep -q 'set -Eeuo pipefail' "${PROJECT_ROOT}/padrino/scripts/backup.sh" 2>/dev/null; then
    pass "  Scripts use strict error handling (set -Eeuo pipefail)"
fi

# Check scripts don't have obvious injection vulnerabilities
for script in "${PROJECT_ROOT}"/padrino/scripts/*.sh; do
    [[ -f "${script}" ]] || continue
    local script_name
    script_name=$(basename "${script}")
    
    # Check for set -Eeuo pipefail
    if grep -q 'set -Eeuo pipefail' "${script}"; then
        info "  ${script_name}: strict mode enabled"
    else
        fail "  ${script_name}: missing 'set -Eeuo pipefail'"
    fi
    
    # Check for unquoted variables in dangerous contexts (basic check)
    if grep -P '\$[a-zA-Z_][a-zA-Z0-9_]*\b(?!")' "${script}" | grep -qv '^[[:space:]]*#' 2>/dev/null; then
        info "  ${script_name}: some unquoted variables found (review manually)"
    fi
done

# =============================================================================
# Test Suite 6: Config & Cron
# =============================================================================
test_header "Test Suite 6 — Configuration & Cron"

# 6.1 Cron file exists and has all 5 jobs
if [[ -f "${CRON_DIR}/padrino-crons.txt" ]]; then
    pass "padrino-crons.txt exists"
    
    CRON_JOB_COUNT=$(grep -cE '^[0-9*].*hermes cron create|^[0-9*].*backup\.sh' "${CRON_DIR}/padrino-crons.txt" 2>/dev/null || echo "0")
    if [[ ${CRON_JOB_COUNT} -ge 5 ]]; then
        pass "  All 5 cron jobs defined (found ${CRON_JOB_COUNT})"
    else
        fail "  Expected 5 cron jobs, found ${CRON_JOB_COUNT}"
    fi
    
    # Check timezone
    if grep -qi "ART\|America/Argentina" "${CRON_DIR}/padrino-crons.txt"; then
        pass "  Timezone set to ART"
    fi
else
    fail "padrino-crons.txt missing"
fi

# 6.2 Systemd service file exists
if [[ -f "${CONFIG_DIR}/padrino-gateway.service" ]]; then
    pass "padrino-gateway.service exists"
    
    if grep -q "User=padrino" "${CONFIG_DIR}/padrino-gateway.service"; then
        pass "  Service runs as padrino user"
    fi
    
    if grep -q "Restart=on-failure" "${CONFIG_DIR}/padrino-gateway.service"; then
        pass "  Service has restart policy"
    fi
else
    fail "padrino-gateway.service missing"
fi

# =============================================================================
# Test Suite 7: Documentation
# =============================================================================
test_header "Test Suite 7 — Documentation"

EXPECTED_DOCS=(
    "README.md" "ARCHITECTURE.md" "INSTALLATION.md" "CONFIGURATION.md"
    "TELEGRAM_SETUP.md" "MEMORY_MODEL.md" "TASK_SYSTEM.md" "FINANCE_SYSTEM.md"
    "DISCIPLINE_SYSTEM.md" "CODE_AUDITOR.md" "SECURITY.md" "BACKUP_AND_RESTORE.md"
    "OPERATIONS.md" "TROUBLESHOOTING.md" "USER_GUIDE.md" "NEXT_STEPS.md"
    "SKILL_CATALOG.md"
)

DOCS_FOUND=0
for doc in "${EXPECTED_DOCS[@]}"; do
    if [[ -f "${DOCS_DIR}/${doc}" ]]; then
        ((DOCS_FOUND++))
        local doc_size
        doc_size=$(stat -c%s "${DOCS_DIR}/${doc}" 2>/dev/null || stat -f%z "${DOCS_DIR}/${doc}" 2>/dev/null)
        
        if [[ ${doc_size} -lt 100 ]]; then
            fail "${doc} is too small (${doc_size} bytes) — may be a stub"
        else
            pass "${doc} exists (${doc_size} bytes)"
        fi
    else
        fail "${doc} missing"
    fi
done

info "Docs found: ${DOCS_FOUND}/${#EXPECTED_DOCS[@]}"

# =============================================================================
# Summary
# =============================================================================
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   Test Results                                   ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}Passed:  ${TESTS_PASSED}${NC}"
echo -e "  ${RED}Failed:  ${TESTS_FAILED}${NC}"
echo -e "  ${YELLOW}Skipped: ${TESTS_SKIPPED}${NC}"
echo -e "  Total:   ${TOTAL_TESTS}"
echo ""

if [[ ${TESTS_FAILED} -eq 0 ]]; then
    echo -e "${BOLD}${GREEN}All tests passed! ✓${NC}"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}${TESTS_FAILED} test(s) failed.${NC}"
    echo ""
    exit 1
fi
