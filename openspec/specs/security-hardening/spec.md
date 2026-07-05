# security-hardening Specification

## Purpose

Harden the Padrino Digital deployment with a dedicated system user, minimal permissions, encrypted secrets, firewall, and execution allowlists. Protect personal data from unauthorized access and prevent the agent from executing dangerous operations.

## Requirements

### Requirement: Dedicated System User with Minimal Permissions

The system MUST run as a dedicated "padrino" system user — never as root. The padrino user SHALL have restrictive umask (077), membership only in its own group, and access ONLY to paths required for operation: ~/.hermes/, padrino.db, scripts/, and designated data directories. The user MUST NOT have sudo rights, SSH key forwarding, or access to /root, /etc/shadow, or other system files.

#### Scenario: Padrino user creation

- GIVEN a fresh Debian/Ubuntu VPS
- WHEN the setup script creates the padrino user
- THEN the user SHALL be created with `useradd -m -s /bin/bash padrino`
- AND umask SHALL be set to 077 in ~/.bashrc
- AND the user SHALL NOT be added to sudo or wheel groups
- AND password login SHALL be disabled (key-only SSH)

#### Scenario: Access denied to /root

- GIVEN the padrino user attempts to read /root
- WHEN the file operation is attempted
- THEN the OS SHALL deny access (permission denied)
- AND the agent SHALL NOT attempt to escalate or use sudo
- AND the agent SHALL report: "No tengo acceso a /root — y no debería tenerlo."

#### Scenario: Write restricted to allowed paths

- GIVEN a skill attempts to write to /etc/cron.d/
- WHEN the write operation is evaluated against the path allowlist
- THEN the system SHALL deny the write
- AND SHALL log the attempt as a security event
- AND SHALL alert: "Intento de escritura fuera de paths permitidos: /etc/cron.d/"

### Requirement: Secrets Management

Secrets (API tokens, encryption keys, credentials) MUST live in a single file with 600 permissions, outside the repository and outside backup archives. The secrets file SHALL be the only source of sensitive configuration. The system MUST NOT log secrets, include them in error messages, or expose them in LLM context.

#### Scenario: Secrets file permissions enforcement

- GIVEN ~/.hermes/secrets.env exists
- WHEN the setup script verifies permissions
- THEN the file SHALL have mode 600 (owner read/write only)
- AND if mode is different, the script SHALL correct it automatically
- AND SHALL log the correction

#### Scenario: Secret excluded from LLM context

- GIVEN the Telegram Bot API token is in secrets.env
- WHEN the LLM processes a user message
- THEN the secrets file contents SHALL NOT be injected into the LLM context
- AND the skill SHALL read the token at invocation time for API calls
- AND the token SHALL never appear in logs or error messages

#### Scenario: Secret exclusion from backup verified

- GIVEN a backup job is about to run
- WHEN the backup script enumerates target paths
- THEN ~/.hermes/secrets.env SHALL be explicitly excluded
- AND a restore SHALL require the user to manually restore the secrets file

### Requirement: Network and Execution Hardening

The system MUST configure UFW firewall allowing only SSH (port 22) and the Hermes gateway port. Outbound connections SHALL be limited to Telegram API, model API, and package repositories. The system SHALL enforce a repo allowlist for code auditor, a command allowlist for script execution, and rate limiting on sensitive operations. Sensitive actions SHALL be audited with timestamp, action, user, and result.

#### Scenario: UFW firewall active

- GIVEN the setup script has completed
- WHEN `ufw status` is checked
- THEN it SHALL show "active"
- AND only ports 22 (SSH) and the configured gateway port SHALL be allowed
- AND all other inbound ports SHALL be denied

#### Scenario: Unauthorized repo rejected by code auditor

- GIVEN the code auditor receives a request to audit "https://github.com/unknown/repo"
- WHEN it checks the repo allowlist
- THEN the repo SHALL NOT be in the allowlist
- AND the audit SHALL be refused with a logged security event
- AND the user SHALL be informed of the rejection

#### Scenario: Sensitive action audit trail

- GIVEN the user approves a financial transaction mutation
- WHEN the mutation executes
- THEN the system SHALL record in the audit log: timestamp, action ("INSERT transaction"), user ("padrino"), result ("success"), and transaction ID
- AND the audit log SHALL be append-only
- AND SHALL be included in backups
