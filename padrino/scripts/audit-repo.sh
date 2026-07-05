#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# audit-repo.sh — Padrino Digital Code Auditor CLI wrapper
# ---------------------------------------------------------------------------
# Takes a repository URL, validates it against the allowlist, clones/updates
# the repo, detects the language, invokes the auditor Hermes profile, and
# outputs the path to the generated OpenCode_TASKS.md.
#
# Usage:
#   bash audit-repo.sh https://github.com/{owner}/{repo}
#   bash audit-repo.sh --full https://github.com/{owner}/{repo}   (skip diff)
#   bash audit-repo.sh --help
#
# Environment variables:
#   AUDITOR_PROFILE   — Hermes profile name (default: auditor)
#   AUDITOR_REPOS_DIR — where repos are cloned (default: ~/repositories)
#   ALLOWLIST_PATH    — path to repo allowlist (default from config)
# ---------------------------------------------------------------------------

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
readonly TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
readonly DATE_STAMP="$(date '+%Y%m%d')"

readonly AUDITOR_PROFILE="${AUDITOR_PROFILE:-auditor}"
readonly AUDITOR_HOME="${HOME}/.hermes_${AUDITOR_PROFILE}"
readonly AUDITOR_REPOS_DIR="${AUDITOR_REPOS_DIR:-${HOME}/repositories}"
readonly ALLOWLIST_PATH="${ALLOWLIST_PATH:-${AUDITOR_HOME}/config/repo-allowlist.txt}"
readonly REPORTS_DIR="${AUDITOR_HOME}/reports/code-audits"
readonly LOG_FILE="${AUDITOR_HOME}/logs/audit-repo.log"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()    { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
success(){ echo -e "  ${GREEN}✓${NC} $*"; }
warning(){ echo -e "  ${YELLOW}⚠${NC} $*"; }
error()  { echo -e "  ${RED}✗${NC} $*" >&2; }
info()   { echo -e "  ${CYAN}→${NC} $*"; }

die() {
    echo -e "${RED}ERROR:${NC} $*" >&2
    exit 1
}

usage() {
    cat <<EOF
${BOLD}audit-repo.sh${NC} — Padrino Digital Code Auditor

${BOLD}Usage:${NC}
  bash audit-repo.sh [OPTIONS] <repo-url>

${BOLD}Options:${NC}
  --full          Perform a full audit (ignore previous diff, analyze all files)
  --dry-run       Validate repo and detect language, but do NOT run analysis
  --help          Show this help message

${BOLD}Arguments:${NC}
  repo-url        HTTPS URL of the repository to audit (e.g. https://github.com/owner/repo)

${BOLD}Environment:${NC}
  AUDITOR_PROFILE    Hermes profile name (default: auditor)
  AUDITOR_REPOS_DIR  Clone destination (default: ~/repositories)
  ALLOWLIST_PATH     Path to repo allowlist

${BOLD}Examples:${NC}
  bash audit-repo.sh https://github.com/juantrix-csv/nexios-backend
  bash audit-repo.sh --full https://github.com/juantrix-csv/nexios-frontend
  bash audit-repo.sh --dry-run https://github.com/juantrix-csv/Ascend-frontend

${BOLD}Exit codes:${NC}
  0 — Audit completed successfully
  1 — Repo not in allowlist or invalid URL
  2 — Clone or analysis failed
  3 — Hermes or required tools not found
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FULL_AUDIT=false
DRY_RUN=false
REPO_URL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)
            FULL_AUDIT=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        -*)
            die "Unknown option: $1. Use --help for usage."
            ;;
        *)
            if [[ -z "${REPO_URL}" ]]; then
                REPO_URL="$1"
            else
                die "Unexpected extra argument: $1"
            fi
            shift
            ;;
    esac
done

if [[ -z "${REPO_URL}" ]]; then
    die "Repository URL is required. Use --help for usage."
fi

# ---------------------------------------------------------------------------
# Validate URL format
# ---------------------------------------------------------------------------
if [[ ! "${REPO_URL}" =~ ^https:// ]]; then
    die "Invalid repo URL: must start with https://"
fi

REPO_URL="${REPO_URL%/}"                     # strip trailing slash
REPO_NAME="$(basename "${REPO_URL}" .git)"   # extract repo name
REPO_DIR="${AUDITOR_REPOS_DIR}/${REPO_NAME}"

log "Audit requested for: ${REPO_URL} (${REPO_NAME})"
log "Mode: $(${FULL_AUDIT} && echo 'FULL' || echo 'INCREMENTAL')"

# ---------------------------------------------------------------------------
# Step 1 — Authorization check
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[1/5] Authorization check${NC}"

if [[ ! -f "${ALLOWLIST_PATH}" ]]; then
    warning "Allowlist not found at: ${ALLOWLIST_PATH}"
    die "Create the allowlist at ${ALLOWLIST_PATH} with authorized repo URLs before auditing."
fi

if ! grep -qF "${REPO_URL}" "${ALLOWLIST_PATH}"; then
    error "Repo NOT in allowlist: ${REPO_URL}"
    echo ""
    echo "  Ese repositorio no está en mi lista de autorizados."
    echo "  Agregalo primero en ${ALLOWLIST_PATH}"
    echo ""
    log "AUDIT REJECTED: ${REPO_URL} not in allowlist"
    exit 1
fi
success "Repo authorized"

# ---------------------------------------------------------------------------
# Step 2 — Ensure directories exist
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[2/5] Environment check${NC}"

mkdir -p "${AUDITOR_REPOS_DIR}" "${REPORTS_DIR}/${REPO_NAME}/${DATE_STAMP}" "$(dirname "${LOG_FILE}")"

# Check Hermes is available
if ! command -v hermes &>/dev/null; then
    die "Hermes CLI not found. Install Hermes Agent first."
fi
success "Hermes CLI available"

# ---------------------------------------------------------------------------
# Step 3 — Clone or update repository (read-only)
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[3/5] Repository clone/update${NC}"

# Source read-only token if available
if [[ -f "${AUDITOR_HOME}/.env" ]]; then
    set +o nounset  # .env may have unset vars
    source <(grep -E '^GIT_READONLY_TOKEN=' "${AUDITOR_HOME}/.env")
    set -o nounset
fi

# Build git clone URL with token if available
if [[ -n "${GIT_READONLY_TOKEN:-}" ]] && [[ "${REPO_URL}" == *"github.com"* ]]; then
    AUTH_URL="${REPO_URL/https:\/\//https:\/\/${GIT_READONLY_TOKEN}@}"
else
    AUTH_URL="${REPO_URL}"
fi

if [[ -d "${REPO_DIR}/.git" ]]; then
    info "Updating existing clone: ${REPO_DIR}"
    git -C "${REPO_DIR}" fetch --depth 1 origin 2>&1 | while IFS= read -r line; do info "  $line"; done
    git -C "${REPO_DIR}" checkout FETCH_HEAD 2>&1 | while IFS= read -r line; do info "  $line"; done
else
    info "Cloning: ${REPO_URL} → ${REPO_DIR}"
    if ! git clone --depth 1 "${AUTH_URL}" "${REPO_DIR}" 2>&1 | while IFS= read -r line; do info "  $line"; done; then
        die "Clone failed. Check that the repo exists and your read-only token is valid."
    fi
fi

CURRENT_COMMIT="$(git -C "${REPO_DIR}" rev-parse HEAD)"
success "Repo at commit: ${CURRENT_COMMIT:0:8}"

# ---------------------------------------------------------------------------
# Step 4 — Detect language and tooling
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[4/5] Language detection${NC}"

detect_language() {
    local dir="$1"
    if [[ -f "${dir}/go.mod" ]]; then
        local fw=""
        grep -qi "gin" "${dir}/go.mod" 2>/dev/null && fw="Gin"
        grep -qi "echo" "${dir}/go.mod" 2>/dev/null && fw="${fw:+${fw}, }Echo"
        grep -qi "chi" "${dir}/go.mod" 2>/dev/null && fw="${fw:+${fw}, }Chi"
        grep -qi "fiber" "${dir}/go.mod" 2>/dev/null && fw="${fw:+${fw}, }Fiber"
        fw="${fw:-Standard library}"
        echo "Go|${fw}"
    elif [[ -f "${dir}/package.json" ]]; then
        local fw=""
        grep -qi '"next"' "${dir}/package.json" 2>/dev/null && fw="Next.js"
        grep -qi '"react"' "${dir}/package.json" 2>/dev/null && fw="${fw:+${fw}, }React"
        grep -qi '"express"' "${dir}/package.json" 2>/dev/null && fw="${fw:+${fw}, }Express"
        grep -qi '"nest"' "${dir}/package.json" 2>/dev/null && fw="${fw:+${fw}, }NestJS"
        fw="${fw:-Node.js}"
        if grep -qi '"typescript"' "${dir}/package.json" 2>/dev/null; then
            echo "TypeScript|${fw}"
        else
            echo "JavaScript|${fw}"
        fi
    elif [[ -f "${dir}/requirements.txt" ]] || [[ -f "${dir}/pyproject.toml" ]]; then
        local fw=""
        grep -qi "django" "${dir}/requirements.txt" "${dir}/pyproject.toml" 2>/dev/null && fw="Django"
        grep -qi "flask" "${dir}/requirements.txt" "${dir}/pyproject.toml" 2>/dev/null && fw="${fw:+${fw}, }Flask"
        grep -qi "fastapi" "${dir}/requirements.txt" "${dir}/pyproject.toml" 2>/dev/null && fw="${fw:+${fw}, }FastAPI"
        fw="${fw:-Python}"
        echo "Python|${fw}"
    elif [[ -f "${dir}/Cargo.toml" ]]; then
        echo "Rust|Cargo"
    elif [[ -f "${dir}/Gemfile" ]]; then
        echo "Ruby|$(grep -q "rails" "${dir}/Gemfile" 2>/dev/null && echo 'Rails' || echo 'Ruby')"
    elif [[ -f "${dir}/pom.xml" ]]; then
        echo "Java|Maven"
    elif [[ -f "${dir}/composer.json" ]]; then
        echo "PHP|Composer"
    else
        echo "unknown|unknown"
    fi
}

LANG_RESULT="$(detect_language "${REPO_DIR}")"
LANG="${LANG_RESULT%%|*}"
FW="${LANG_RESULT##*|}"

if [[ "${LANG}" == "unknown" ]]; then
    warning "Could not detect language. The repo may not contain code."
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "  Dry run complete — no language detected."
        exit 0
    fi
    # Continue anyway — Hermes auditor can still do grep-based analysis
fi

success "Detected: ${LANG}${FW:+, ${FW}}"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo ""
    echo -e "${BOLD}Dry run complete.${NC}"
    echo "  Repo:       ${REPO_URL}"
    echo "  Commit:     ${CURRENT_COMMIT:0:8}"
    echo "  Language:   ${LANG}"
    echo "  Framework:  ${FW}"
    echo "  Local path: ${REPO_DIR}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 5 — Run safe static analysis tools
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}[5/5] Static analysis${NC}"

ANALYSIS_DIR="${REPORTS_DIR}/${REPO_NAME}/${DATE_STAMP}"
TOOL_OUTPUT="${ANALYSIS_DIR}/tool-output.txt"
: > "${TOOL_OUTPUT}"

run_safe_tool() {
    local name="$1"
    local cmd="$2"
    info "Running ${name}..."
    if command -v "${cmd%% *}" &>/dev/null; then
        if eval "${cmd}" >> "${TOOL_OUTPUT}" 2>&1; then
            success "${name} — no issues found"
        else
            success "${name} — issues found (see tool-output.txt)"
        fi
    else
        warning "${name} — not installed (skipped)"
        echo "[SKIPPED] ${name} — tool not installed" >> "${TOOL_OUTPUT}"
    fi
}

case "${LANG}" in
    Go)
        run_safe_tool "go vet"     "cd ${REPO_DIR} && go vet ./... 2>&1"
        run_safe_tool "staticcheck" "cd ${REPO_DIR} && staticcheck ./... 2>&1 || true"
        run_safe_tool "golangci-lint" "cd ${REPO_DIR} && golangci-lint run --no-fix ./... 2>&1 || true"
        ;;
    TypeScript|JavaScript)
        run_safe_tool "eslint"     "cd ${REPO_DIR} && npx eslint . --no-fix 2>&1 || true"
        if [[ "${LANG}" == "TypeScript" ]]; then
            run_safe_tool "tsc"    "cd ${REPO_DIR} && npx tsc --noEmit 2>&1 || true"
        fi
        ;;
    Python)
        run_safe_tool "ruff"       "cd ${REPO_DIR} && ruff check . 2>&1 || true"
        run_safe_tool "bandit"     "cd ${REPO_DIR} && bandit -r . -ll 2>&1 || true"
        run_safe_tool "mypy"       "cd ${REPO_DIR} && mypy . 2>&1 || true"
        ;;
    *)
        info "No language-specific tools available for ${LANG}. Running grep-based checks."
        ;;
esac

# Universal checks (run for all languages)
run_safe_tool "grep:secrets" "grep -rInI --include='*.*' -E '(API_KEY|SECRET|TOKEN|PASSWORD|private.key)' ${REPO_DIR} --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=vendor 2>/dev/null || true"
run_safe_tool "grep:todos"   "grep -rInI --include='*.*' -E '(TODO|FIXME|HACK|XXX|TEMP)' ${REPO_DIR} --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=vendor 2>/dev/null || true"

# ---------------------------------------------------------------------------
# Step 6 — Invoke Hermes auditor profile
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}Invoking Hermes auditor profile...${NC}"

# Build the audit command for the Hermes profile
if [[ "${FULL_AUDIT}" == "true" ]]; then
    AUDIT_PROMPT="Audita el repositorio ${REPO_URL} en ${REPO_DIR}. Es una auditoría COMPLETA (no incremental). Lenguaje: ${LANG}. Framework: ${FW}. Commit actual: ${CURRENT_COMMIT}. Los resultados de herramientas estáticas están en ${TOOL_OUTPUT}. Generá hallazgos estructurados y OpenCode_TASKS.md en ${ANALYSIS_DIR}."
else
    AUDIT_PROMPT="Audita el repositorio ${REPO_URL} en ${REPO_DIR}. Es una auditoría INCREMENTAL (solo diff desde el commit anterior registrado en audit_runs). Lenguaje: ${LANG}. Framework: ${FW}. Commit actual: ${CURRENT_COMMIT}. Los resultados de herramientas estáticas están en ${TOOL_OUTPUT}. Generá hallazgos estructurados y OpenCode_TASKS.md en ${ANALYSIS_DIR}."
fi

echo ""
info "Audit prompt sent to profile '${AUDITOR_PROFILE}'"
info "Report directory: ${ANALYSIS_DIR}"
echo ""

# Invoke Hermes with the auditor profile
if hermes -p "${AUDITOR_PROFILE}" chat -q "${AUDIT_PROMPT}" --no-telegram 2>&1 | while IFS= read -r line; do
    echo "  ${line}"
done; then
    echo ""
    success "Audit completed"
else
    echo ""
    error "Hermes auditor encountered an error"
    log "AUDIT FAILED for ${REPO_URL}"
    exit 2
fi

# ---------------------------------------------------------------------------
# Step 7 — Report output path
# ---------------------------------------------------------------------------
echo ""
if [[ -f "${ANALYSIS_DIR}/OpenCode_TASKS.md" ]]; then
    echo -e "${BOLD}${GREEN}Audit report ready:${NC}"
    echo "  ${ANALYSIS_DIR}/OpenCode_TASKS.md"
    echo ""
    log "AUDIT COMPLETED: ${REPO_URL} → ${ANALYSIS_DIR}/OpenCode_TASKS.md"
else
    warning "OpenCode_TASKS.md not found at expected path."
    warning "Check ${ANALYSIS_DIR}/ for output files."
    log "AUDIT COMPLETED with warning: OpenCode_TASKS.md not found for ${REPO_URL}"
fi

echo -e "\n${BOLD}Done.${NC} Review the report and feed OpenCode_TASKS.md to an OpenCode session for implementation."
