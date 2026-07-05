# Padrino Digital — Auditor Profile Setup

## What is the Auditor Profile?

The auditor profile is a **separate Hermes Agent identity** that can only audit
code. It has no Telegram gateway, no access to your personal data, and uses
read-only git tokens. This isolation prevents the code auditor from accidentally
modifying audited repositories or accessing your finances, diary, or memories.

## Quick Setup

### 1. Create the auditor profile directory

```bash
mkdir -p ~/.hermes_auditor/{skills,config,reports,memory,logs}
```

### 2. Copy the skill and persona

```bash
cp padrino/auditor-profile/SOUL.md ~/.hermes_auditor/SOUL.md
cp -r padrino/skills/padrino-audit ~/.hermes_auditor/skills/
```

### 3. Copy and configure the environment

```bash
cp padrino/auditor-profile/config/.env.template ~/.hermes_auditor/.env
chmod 600 ~/.hermes_auditor/.env
nano ~/.hermes_auditor/.env   # Fill in GIT_READONLY_TOKEN
```

### 4. Copy the repo allowlist

```bash
cp padrino/config/repo-allowlist.txt ~/.hermes_auditor/config/repo-allowlist.txt
# Edit to add your authorized repos
```

### 5. Install analysis tools (optional, per language)

```bash
# Go tools
go install honnef.co/go/tools/cmd/staticcheck@latest
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Python tools
pip3 install --user ruff bandit mypy

# Node.js tools (only if Node is installed)
npm install -g eslint
```

### 6. Test the auditor

```bash
hermes -p auditor chat -q "audit repo https://github.com/juantrix-csv/nexios-backend"
```

## Isolation Guarantees

| Resource | Auditor Profile | Main Padrino |
|----------|:---:|:---:|
| Telegram gateway | ❌ | ✅ |
| Write to audited repos | ❌ | ❌ |
| Read padrino.db | ❌ | ✅ |
| Access memory/ | ❌ | ✅ |
| Read finances | ❌ | ✅ |
| Send Telegram alerts | ❌ | ✅ |
| Write audit reports | ✅ | ❌ |

## Git Token Requirements

Your `GIT_READONLY_TOKEN` must be a **fine-grained personal access token** with:

- **Repository access**: "Only select repositories" (choose your audited repos)
- **Permissions**:
  - `Contents`: Read-only
  - `Metadata`: Read-only
- **NO other permissions**

Create it at: https://github.com/settings/tokens?type=beta

## Invoking the Auditor

### From the VPS (CLI)

```bash
hermes -p auditor chat -q "audit repo https://github.com/juantrix-csv/nexios-backend"
```

### From Padrino Digital (Telegram)

```
/auditar https://github.com/juantrix-csv/nexios-backend
```

Padrino will forward the request to the auditor profile via CLI.

## Report Location

```
~/.hermes_auditor/reports/code-audits/
├── {repo-name}/
│   ├── {date}/
│   │   ├── OpenCode_TASKS.md      # Implementation tasks for OpenCode
│   │   ├── findings.json           # Machine-readable findings
│   │   └── audit.log               # Execution log
```

## Security Notes

- The `.env` file is chmod 600 — only the auditor user can read it
- The git token is read-only — even if compromised, repos cannot be modified
- The auditor profile has NO network access beyond git clone
- Reports are stored locally on the VPS, never uploaded
