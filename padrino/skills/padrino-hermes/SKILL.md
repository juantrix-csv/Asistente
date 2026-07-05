---
name: padrino-hermes
description: Use when setting up, troubleshooting, or verifying the Hermes Agent installation, Telegram gateway, and systemd service for Padrino Digital.
version: 1.0.0
author: Padrino Digital
license: MIT
metadata:
  hermes:
    tags: [padrino, hermes, telegram, gateway, installation, systemd]
    related_skills: [padrino-security]
---

# padrino-hermes — Hermes Agent & Telegram Gateway

## Purpose

Install, configure, and maintain the Hermes Agent v0.18.0 foundation that
powers Padrino Digital. This skill covers the full lifecycle: installation
on Debian/Ubuntu, Telegram Bot API gateway setup, systemd service management,
healthchecks, and troubleshooting.

## When to Use

- User asks to install or update Hermes Agent
- User wants to configure the Telegram gateway
- Hermes gateway is not responding or crashed
- User asks to check gateway status or run healthchecks
- After a VPS reboot — verify everything came back up

---

## Installation

### Prerequisites

Before installing, verify the host meets these minimums:

- **OS**: Debian 12+ or Ubuntu 22.04+
- **Python**: 3.11 or later (`python3 --version`)
- **SQLite**: 3.35 or later with FTS5 (`sqlite3 --version`)
- **System user**: dedicated `padrino` user (created by `setup.sh`)
- **Root access**: required only for initial `setup.sh`; Hermes runs as `padrino`

### Automated Install (Recommended)

Run the idempotent setup script:

```bash
sudo bash /srv/padrino/scripts/setup.sh
```

This handles: user creation, directory structure, dependency checks,
Hermes clone + install, systemd service, and UFW firewall.

### Manual Install (Fallback)

If the automated script is not available:

```bash
# 1. Verify the padrino user exists
id padrino

# 2. Clone Hermes v0.18.0
sudo -u padrino git clone --depth 1 --branch v0.18.0 \
    https://github.com/NousResearch/Hermes-Function-Calling.git \
    /home/padrino/hermes-agent

# 3. Install Python dependencies
cd /home/padrino/hermes-agent
sudo -u padrino pip3 install --user -r requirements.txt

# 4. Verify the install
sudo -u padrino /home/padrino/hermes-agent/hermes --version
# Expected output: v0.18.0
```

---

## Telegram Gateway Setup

### Step 1: Get a Bot Token

1. Open Telegram and chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Save the token — it looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Create the Secrets File

```bash
# As padrino user
mkdir -p /home/padrino/.hermes
cat > /home/padrino/.hermes/.env << 'EOF'
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ALLOWED_USERS=your_telegram_user_id
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-your-api-key
TZ=America/Argentina/Buenos_Aires
EOF

# CRITICAL: lock down the secrets file
chmod 600 /home/padrino/.hermes/.env
```

### Step 3: Test the Gateway

```bash
# Start the gateway
sudo systemctl start hermes-gateway

# Check it's running
sudo systemctl status hermes-gateway

# Send a test message to your bot on Telegram
# Expected: the bot responds within 5 seconds
```

### Step 4: Enable on Boot

```bash
sudo systemctl enable hermes-gateway
```

---

## Systemd Service Management

All service commands require `sudo`:

| Action | Command |
|--------|---------|
| Start | `sudo systemctl start hermes-gateway` |
| Stop | `sudo systemctl stop hermes-gateway` |
| Restart | `sudo systemctl restart hermes-gateway` |
| Status | `sudo systemctl status hermes-gateway` |
| Enable | `sudo systemctl enable hermes-gateway` |
| Disable | `sudo systemctl disable hermes-gateway` |
| Logs | `sudo journalctl -u hermes-gateway -f` |
| Logs (last 100) | `sudo journalctl -u hermes-gateway -n 100` |

### Service Properties

- **Runs as**: `padrino:padrino` (never root)
- **Restart policy**: `on-failure`, 10-second delay
- **Security hardening**: `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=read-only`
- **Writable paths**: `/srv/padrino`, `/home/padrino/.hermes`
- **Home directory**: `/home/padrino`

---

## Healthcheck

Run the healthcheck script to verify everything is operational:

```bash
sudo -u padrino bash /srv/padrino/scripts/healthcheck.sh
```

What it checks:

1. **Hermes gateway process** — is the systemd service running?
2. **Telegram connectivity** — does the bot respond to a ping?
3. **Disk space** — is there enough free space?
4. **Padrino directories** — are all required directories accessible?

Exit codes:
- `0` — all checks passed (healthy)
- Non-zero — one or more checks failed (see output for details)

---

## Troubleshooting

### Gateway not starting

```bash
# Check the service logs
sudo journalctl -u hermes-gateway -n 50 --no-pager

# Verify the secrets file exists and has correct permissions
ls -la /home/padrino/.hermes/.env
# Expected: -rw------- (600)

# Verify the bot token is valid
# Send a GET request to Telegram API:
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
# Should return JSON with bot info, NOT an error
```

### Bot not responding to messages

```bash
# Check if Hermes sees incoming messages
sudo journalctl -u hermes-gateway -f

# Verify the Telegram webhook or polling is configured
# Check your bot's webhook status:
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

### Service crashes after reboot

```bash
# Verify the service is enabled
sudo systemctl is-enabled hermes-gateway
# Expected: enabled

# Check boot logs
sudo journalctl -u hermes-gateway -b

# Verify network-online.target is reached before Hermes starts
sudo systemctl status network-online.target
```

### Permission denied errors

```bash
# Verify padrino user owns the data directories
ls -la /srv/padrino/
# Expected: padrino:padrino

# Fix ownership if needed
sudo chown -R padrino:padrino /srv/padrino

# Verify .env permissions
chmod 600 /home/padrino/.hermes/.env
chown padrino:padrino /home/padrino/.hermes/.env
```

---

## Quick Reference

### Verify Everything is Healthy

```bash
# 1. Check service
sudo systemctl status hermes-gateway

# 2. Run healthcheck
sudo -u padrino bash /srv/padrino/scripts/healthcheck.sh

# 3. Check recent logs
sudo journalctl -u hermes-gateway -n 20 --no-pager
```

### Restart After Config Change

```bash
sudo systemctl restart hermes-gateway
# Wait 2 seconds, then verify
sleep 2
sudo systemctl status hermes-gateway
```

### Update Hermes (Manual)

```bash
cd /home/padrino/hermes-agent
sudo -u padrino git fetch --tags
sudo -u padrino git checkout v0.18.1  # or latest tag
sudo -u padrino pip3 install --user -r requirements.txt
sudo systemctl restart hermes-gateway
```
