# hermes-integration Specification

## Purpose

Install and configure Hermes Agent v0.18.0 on a Debian/Ubuntu VPS as the foundation layer for Padrino Digital — Telegram gateway, model routing, systemd service, and CLI tooling.

## Requirements

### Requirement: Hermes v0.18.0 Installation

The system MUST install Hermes Agent v0.18.0 from the Nous Research GitHub repository onto a Debian/Ubuntu VPS. The installation SHALL run as the dedicated non-root user "padrino". Python 3.11+ and SQLite 3.35+ MUST be verified before installation proceeds.

#### Scenario: Fresh install on Debian 12

- GIVEN a Debian 12 VPS with Python 3.11 and SQLite 3.40 installed
- AND a dedicated "padrino" system user exists
- WHEN the setup script executes
- THEN Hermes v0.18.0 SHALL be cloned and installed under /home/padrino/hermes-agent
- AND `hermes --version` SHALL report v0.18.0
- AND the installation SHALL complete without root privileges

#### Scenario: Install fails on missing Python version

- GIVEN a VPS with Python 3.9 installed (below minimum 3.11)
- WHEN the setup script executes
- THEN the script SHALL detect the version mismatch
- AND SHALL exit with a clear error message stating the required and found versions
- AND SHALL NOT proceed with installation

#### Scenario: Install fails on missing SQLite FTS5

- GIVEN a VPS where SQLite was compiled without FTS5 support
- WHEN the setup script verifies dependencies
- THEN the script SHALL detect the missing FTS5 extension
- AND SHALL exit with instructions to reinstall SQLite with FTS5 enabled

### Requirement: Telegram Gateway Setup

The system MUST configure Hermes' Telegram gateway so Padrino Digital can send and receive messages through Telegram. The gateway SHALL authenticate via a Telegram Bot API token stored in a secrets file with 600 permissions. Messages MUST be received and responded to within 5 seconds under normal load.

#### Scenario: Gateway setup with valid token

- GIVEN a valid Telegram Bot API token is stored in a 600-permission secrets file
- AND Hermes v0.18.0 is installed
- WHEN the gateway setup command executes
- THEN the Telegram gateway SHALL connect successfully
- AND a test message sent to the bot SHALL receive a response within 5 seconds

#### Scenario: Gateway fails with invalid token

- GIVEN an invalid or expired Telegram Bot API token
- WHEN the gateway setup command executes
- THEN the system SHALL report authentication failure
- AND SHALL NOT silently retry indefinitely
- AND SHALL surface the specific error from Telegram's API

#### Scenario: Gateway survives system reboot

- GIVEN the Telegram gateway is running via systemd
- WHEN the VPS reboots
- THEN the gateway service SHALL restart automatically
- AND SHALL re-establish Telegram connectivity without manual intervention
- AND `systemctl status hermes-gateway` SHALL show active (running)

### Requirement: Systemd Service with Dedicated User

Hermes Agent MUST run as a systemd service under the dedicated "padrino" user. The service SHALL start on boot, restart on failure, and log to journald. The service unit file SHALL NOT grant any capabilities beyond what the padrino user already has.

#### Scenario: Service starts on boot

- GIVEN hermes-gateway.service is enabled
- WHEN the VPS boots
- THEN the service SHALL start automatically
- AND Hermes SHALL begin listening for Telegram messages

#### Scenario: Service restarts on failure

- GIVEN the hermes-gateway.service is running
- WHEN the Hermes process crashes
- THEN systemd SHALL restart the service within 10 seconds
- AND the restart SHALL be logged to journald with the failure reason

#### Scenario: Service runs as non-root user

- GIVEN hermes-gateway.service is running
- WHEN checking the process owner
- THEN the process SHALL run as user "padrino"
- AND SHALL NOT run as root under any circumstance
