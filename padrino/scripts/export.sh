#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# export.sh — Padrino Digital data export
# ---------------------------------------------------------------------------
# Exports Padrino Digital data to portable formats:
#   - Finance transactions → CSV (UTF-8 with BOM)
#   - Memory entries → JSON or Markdown
#   - Tasks → CSV
#
# Usage:
#   bash export.sh finance [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--output path]
#   bash export.sh memory [--format json|markdown] [--output path]
#   bash export.sh tasks [--status active|done|all] [--output path]
#   bash export.sh all [--output-dir path]
#
# Environment:
#   None required (uses sqlite3 directly)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly PADRINO_DATA="/srv/padrino/data"
readonly PADRINO_DB="${PADRINO_DATA}/padrino.db"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
readonly DATE_STAMP="$(date '+%Y%m%d-%H%M%S')"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
success(){ echo -e "  ${GREEN}✓${NC} $*"; }
error()  { echo -e "  ${RED}✗${NC} $*" >&2; }
info()   { echo -e "  ${CYAN}→${NC} $*"; }

die() {
    echo -e "${RED}ERROR:${NC} $*" >&2
    exit 1
}

usage() {
    cat <<EOF
${BOLD}export.sh${NC} — Padrino Digital Data Export

${BOLD}Usage:${NC}
  bash export.sh <type> [options]

${BOLD}Export types:${NC}
  finance      Export transactions to CSV
  memory       Export memory entries to JSON or Markdown
  tasks        Export tasks to CSV
  all          Export all of the above

${BOLD}Options:${NC}
  --output PATH        Output file path
  --output-dir PATH    Output directory (for 'all')
  --from YYYY-MM-DD    Start date filter (finance, tasks)
  --to YYYY-MM-DD      End date filter (finance, tasks)
  --format FORMAT      Output format: csv (default for finance/tasks), json, markdown
  --status STATUS      Task status filter: active, done, all (default: active)
  --help               Show this help

${BOLD}Examples:${NC}
  bash export.sh finance --from 2026-06-01 --to 2026-06-30
  bash export.sh memory --format markdown --output memoria.md
  bash export.sh tasks --status done --output tareas_completadas.csv
  bash export.sh all --output-dir ./exports/
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
if [[ ! -f "${PADRINO_DB}" ]]; then
    die "Database not found: ${PADRINO_DB}"
fi

if ! command -v sqlite3 &>/dev/null; then
    die "sqlite3 is not installed."
fi

# ---------------------------------------------------------------------------
# CSV helper — writes UTF-8 BOM + header + rows
# ---------------------------------------------------------------------------
write_csv() {
    local output="$1"
    local query="$2"
    local header="$3"
    
    # UTF-8 BOM for Excel compatibility
    printf '\xEF\xBB\xBF' > "${output}"
    echo "${header}" >> "${output}"
    sqlite3 -csv -header "${PADRINO_DB}" "${query}" | tail -n +2 >> "${output}"
}

# ---------------------------------------------------------------------------
# Finance export
# ---------------------------------------------------------------------------
export_finance() {
    local output="${OUTPUT_FILE:-${PROJECT_ROOT}/padrino/exports/finance-${DATE_STAMP}.csv}"
    local from="${FROM_DATE:-}"
    local to="${TO_DATE:-}"
    local where=""
    
    [[ -n "${from}" ]] && where="${where} AND date >= '${from}'"
    [[ -n "${to}" ]]   && where="${where} AND date <= '${to}'"
    
    info "Exporting transactions to CSV..."
    mkdir -p "$(dirname "${output}")"
    
    local query="SELECT id, type, amount, currency, category, account, business_area,
                 payment_method, date, description, recurring,
                 original_currency, original_amount, conversion_rate, created_at
                 FROM transactions WHERE 1=1 ${where} ORDER BY date DESC;"
    
    write_csv "${output}" "${query}" \
        "id,type,amount,currency,category,account,business_area,payment_method,date,description,recurring,original_currency,original_amount,conversion_rate,created_at"
    
    local count
    count=$(sqlite3 "${PADRINO_DB}" "SELECT COUNT(*) FROM transactions WHERE 1=1 ${where};")
    
    success "Exported ${count} transactions to ${output}"
    echo "${output}"
}

# ---------------------------------------------------------------------------
# Memory export
# ---------------------------------------------------------------------------
export_memory() {
    local format="${EXPORT_FORMAT:-markdown}"
    local output=""
    
    case "${format}" in
        json)
            output="${OUTPUT_FILE:-${PROJECT_ROOT}/padrino/exports/memory-${DATE_STAMP}.json}"
            info "Exporting memories to JSON..."
            mkdir -p "$(dirname "${output}")"
            
            sqlite3 -json "${PADRINO_DB}" \
                "SELECT id, content, source, confidence, type, area, project, tags, created_at
                 FROM memories ORDER BY created_at DESC;" > "${output}"
            ;;
        markdown|md)
            output="${OUTPUT_FILE:-${PROJECT_ROOT}/padrino/exports/memory-${DATE_STAMP}.md}"
            info "Exporting memories to Markdown..."
            mkdir -p "$(dirname "${output}")"
            
            {
                echo "# Padrino Digital — Memory Export"
                echo "**Date**: $(date '+%Y-%m-%d %H:%M:%S')"
                echo ""
                
                sqlite3 -separator "|" "${PADRINO_DB}" \
                    "SELECT id, source, confidence, type, area, created_at, content
                     FROM memories ORDER BY created_at DESC;" | while IFS='|' read -r id source confidence type area created_at content; do
                    echo "## Memory #${id}"
                    echo "**Source**: ${source} | **Confidence**: ${confidence} | **Type**: ${type}"
                    echo "**Area**: ${area:-N/A} | **Date**: ${created_at}"
                    echo ""
                    echo "${content}"
                    echo ""
                    echo "---"
                    echo ""
                done
            } > "${output}"
            ;;
        *)
            die "Unknown format: ${format}. Use json or markdown."
            ;;
    esac
    
    local count
    count=$(sqlite3 "${PADRINO_DB}" "SELECT COUNT(*) FROM memories;")
    
    success "Exported ${count} memories to ${output}"
    echo "${output}"
}

# ---------------------------------------------------------------------------
# Tasks export
# ---------------------------------------------------------------------------
export_tasks() {
    local status="${TASK_STATUS:-active}"
    local output="${OUTPUT_FILE:-${PROJECT_ROOT}/padrino/exports/tasks-${DATE_STAMP}.csv}"
    local where=""
    
    case "${status}" in
        active) where="AND status NOT IN ('done', 'cancelled', 'archived')" ;;
        done)   where="AND status = 'done'" ;;
        all)    where="" ;;
        *)      die "Unknown status filter: ${status}. Use active, done, or all." ;;
    esac
    
    info "Exporting tasks (${status}) to CSV..."
    mkdir -p "$(dirname "${output}")"
    
    local query="SELECT id, title, status, priority, project_id, due_at, scheduled_at,
                 estimated_minutes, actual_minutes, snooze_count, source, created_at, updated_at
                 FROM tasks WHERE 1=1 ${where} ORDER BY priority DESC, due_at ASC;"
    
    write_csv "${output}" "${query}" \
        "id,title,status,priority,project_id,due_at,scheduled_at,estimated_minutes,actual_minutes,snooze_count,source,created_at,updated_at"
    
    local count
    count=$(sqlite3 "${PADRINO_DB}" "SELECT COUNT(*) FROM tasks WHERE 1=1 ${where};")
    
    success "Exported ${count} tasks to ${output}"
    echo "${output}"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
EXPORT_TYPE=""
OUTPUT_FILE=""
OUTPUT_DIR=""
FROM_DATE=""
TO_DATE=""
EXPORT_FORMAT="csv"
TASK_STATUS="active"

while [[ $# -gt 0 ]]; do
    case "$1" in
        finance|memory|tasks|all)
            EXPORT_TYPE="$1"
            shift
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --from)
            FROM_DATE="$2"
            shift 2
            ;;
        --to)
            TO_DATE="$2"
            shift 2
            ;;
        --format)
            EXPORT_FORMAT="$2"
            shift 2
            ;;
        --status)
            TASK_STATUS="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

if [[ -z "${EXPORT_TYPE}" ]]; then
    die "Export type is required. Use: finance, memory, tasks, or all"
fi

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}Padrino Digital — Data Export${NC}"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

case "${EXPORT_TYPE}" in
    finance) export_finance ;;
    memory)  export_memory ;;
    tasks)   export_tasks ;;
    all)
        echo -e "${BOLD}Exporting all data types...${NC}"
        echo ""
        
        if [[ -n "${OUTPUT_DIR}" ]]; then
            mkdir -p "${OUTPUT_DIR}"
        fi
        
        OUTPUT_FILE="${OUTPUT_DIR:+${OUTPUT_DIR}/}finance-${DATE_STAMP}.csv"
        FINANCE_PATH=$(export_finance)
        
        OUTPUT_FILE="${OUTPUT_DIR:+${OUTPUT_DIR}/}memory-${DATE_STAMP}.md"
        EXPORT_FORMAT="markdown"
        MEMORY_PATH=$(export_memory)
        
        OUTPUT_FILE="${OUTPUT_DIR:+${OUTPUT_DIR}/}tasks-${DATE_STAMP}.csv"
        TASK_STATUS="all"
        TASKS_PATH=$(export_tasks)
        
        echo ""
        success "All exports complete."
        echo ""
        echo "  Finance:  ${FINANCE_PATH}"
        echo "  Memory:   ${MEMORY_PATH}"
        echo "  Tasks:    ${TASKS_PATH}"
        ;;
esac

echo ""
echo -e "${GREEN}Done.${NC}"
