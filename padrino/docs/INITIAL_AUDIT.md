# Initial VPS Audit — Padrino Digital

> **Status**: [TO BE FILLED ON VPS]
>
> Run `scripts/security-audit.sh` on the VPS and copy the output into the
> sections below. This document serves as the baseline security snapshot
> before Padrino Digital goes live.

---

## System Information

| Field | Value |
|-------|-------|
| Hostname | [TO BE FILLED ON VPS] |
| OS | [TO BE FILLED ON VPS] |
| Kernel | [TO BE FILLED ON VPS] |
| Uptime | [TO BE FILLED ON VPS] |
| Date of audit | [TO BE FILLED ON VPS] |

---

## Resources

| Resource | Value |
|----------|-------|
| CPU cores | [TO BE FILLED ON VPS] |
| Total RAM | [TO BE FILLED ON VPS] |
| Disk total | [TO BE FILLED ON VPS] |
| Disk used | [TO BE FILLED ON VPS] |
| Disk available | [TO BE FILLED ON VPS] |

---

## Services

| Service | Status | Notes |
|---------|--------|-------|
| SSH | [TO BE FILLED ON VPS] | Must be key-only, port 22 |
| UFW | [TO BE FILLED ON VPS] | Must be active |
| cron | [TO BE FILLED ON VPS] | Must be running |
| systemd-journald | [TO BE FILLED ON VPS] | Must be running |

---

## Hermes Agent Status

| Check | Result | Notes |
|-------|--------|-------|
| Hermes installed | [TO BE FILLED ON VPS] | Expected: v0.18.0 |
| Gateway running | [TO BE FILLED ON VPS] | Expected: active (running) |
| Telegram connectivity | [TO BE FILLED ON VPS] | Bot must respond |
| Python version | [TO BE FILLED ON VPS] | Expected: >= 3.11 |
| SQLite version | [TO BE FILLED ON VPS] | Expected: >= 3.35 with FTS5 |

---

## Security Checks

| Check | Pass | Notes |
|-------|------|-------|
| Dedicated padrino user exists | [TO BE FILLED ON VPS] | uid >= 1000 |
| Padrino NOT in sudo/wheel | [TO BE FILLED ON VPS] | Security requirement |
| umask is 077 | [TO BE FILLED ON VPS] | Set in ~/.bashrc |
| SSH key-only auth | [TO BE FILLED ON VPS] | No password login |
| UFW active | [TO BE FILLED ON VPS] | Only SSH + gateway |
| No secrets in repo | [TO BE FILLED ON VPS] | Check all files |
| Sensitive paths blocked | [TO BE FILLED ON VPS] | Refer to sensitive-paths.txt |
| .env permissions 600 | [TO BE FILLED ON VPS] | Secrets file |

---

## Risks Identified

[TO BE FILLED ON VPS]

List any security concerns discovered during the audit that need remediation
before Padrino Digital can go live.

---

## Decisions Made

[TO BE FILLED ON VPS]

Record any architecture or configuration decisions made during or as a result
of this audit.

---

## Signature

| Role | Name | Date |
|------|------|------|
| Auditor | [TO BE FILLED ON VPS] | [TO BE FILLED ON VPS] |
| Reviewer | [TO BE FILLED ON VPS] | [TO BE FILLED ON VPS] |
