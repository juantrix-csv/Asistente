# Troubleshooting — Padrino Digital

Problemas comunes y sus soluciones.

## El bot no responde en Telegram

### Verificar el gateway

```bash
sudo systemctl status hermes-gateway
```

Si no está `active (running)`:
```bash
sudo -u padrino bash padrino/scripts/restart.sh
sudo journalctl -u hermes-gateway -n 30 --no-pager
```

### Verificar el webhook

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Debe mostrar `"ok":true` y la URL correcta. Si no:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<VPS_IP>:8443/telegram"
```

### Verificar conectividad

```bash
# ¿El puerto está abierto?
sudo ufw status

# ¿El VPS es accesible?
curl -k https://<VPS_IP>:8443/telegram
# Debe responder algo (aunque sea un error, significa que llega)
```

### Verificar el token

```bash
# ¿El token es válido?
curl "https://api.telegram.org/bot<TOKEN>/getMe"
# Debe devolver los datos del bot
```

## Error "PADRINO_BACKUP_KEY no definida"

```bash
# Verificar que existe
cat ~/.hermes/secrets.env | grep PADRINO_BACKUP_KEY

# Si no existe, crearla
echo "PADRINO_BACKUP_KEY=una-frase-secreta-larga" >> ~/.hermes/secrets.env
chmod 600 ~/.hermes/secrets.env

# Cargarla en la sesión actual
source ~/.hermes/secrets.env
```

## Backup falla

```bash
# Ver el log
tail -50 /srv/padrino/logs/backup.log
```

### "Espacio insuficiente"

```bash
# Ver espacio
df -h /srv/padrino/backups/

# Borrar backups viejos
find /srv/padrino/backups/ -name "*.tar.gz.gpg" -mtime +30 -delete

# O reducir retención en padrino/config/retention.conf
```

### "GPG no instalado"

```bash
sudo apt install gnupg
```

### "sqlite3 no encontrado"

```bash
sudo apt install sqlite3
```

## Restauración falla

### "Checksum no coincide"

El backup está corrupto. Intentar con una fecha anterior:

```bash
bash padrino/scripts/restore.sh --list   # Ver disponibles
bash padrino/scripts/restore.sh 2026-07-03  # Una fecha anterior
```

### "PRAGMA integrity_check falló"

La base de datos restaurada está corrupta. Restaurar desde otro backup.

### "No puedo confirmar en modo no-interactivo"

La restauración requiere confirmación interactiva. Ejecutar manualmente:

```bash
bash padrino/scripts/restore.sh 2026-07-04
# Cuando pregunte "¿Confirmás?", escribir: SI-RESTAURAR
```

## Base de datos corrupta

```bash
# Verificar integridad
sqlite3 /srv/padrino/data/padrino.db "PRAGMA integrity_check;"

# Si no es "ok", intentar recuperar:
sqlite3 /srv/padrino/data/padrino.db ".recover" > /tmp/padrino-recovered.sql

# Restaurar desde backup (más seguro)
bash padrino/scripts/restore.sh --latest
```

## Rate limiting — "Ya hiciste X operaciones"

Esperar que pase la ventana de rate limit (1 hora para transacciones, 1 día para restore).

Si es urgente, los rate limits están en `padrino-security/SKILL.md` — modificar
con precaución.

## Cambios en skills no se reflejan

```bash
# 1. Verificar que el archivo se guardó
cat ~/.hermes/skills/padrino-plan/SKILL.md | head -5

# 2. Reiniciar el gateway
sudo -u padrino bash padrino/scripts/restart.sh

# 3. Verificar que no haya errores de parseo
sudo journalctl -u hermes-gateway -n 20 --no-pager
```

## El auditor rechaza un repo

Verificar que el repo está en la allowlist:

```bash
cat padrino/config/repo-allowlist.txt
# o
cat ~/.hermes_auditor/config/repo-allowlist.txt
```

Agregar el repo:
```bash
echo "https://github.com/usuario/repo" >> padrino/config/repo-allowlist.txt
```

## Cron jobs no se ejecutan

```bash
# Verificar crontab instalado
crontab -u padrino -l

# Verificar logs de cron
sudo grep CRON /var/log/syslog | tail -20

# Verificar que hermes está en el PATH del cron
sudo -u padrino which hermes

# Si no, usar path completo en padrino-crons.txt:
# /home/padrino/hermes-agent/hermes cron create ...
```

## El gateway se cae seguido

```bash
# Ver memory
free -h

# Ver CPU
top -bn1 | head -5

# Ver logs de systemd
sudo journalctl -u hermes-gateway --since "1 hour ago" --no-pager

# Aumentar memoria swap si es necesario
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## No puedo conectarme por SSH

```bash
# ¿IP correcta?
# ¿Puerto 22 abierto en UFW?
sudo ufw status

# ¿Servicio SSH corriendo?
sudo systemctl status sshd

# Ver intentos fallidos
sudo grep "Failed password" /var/log/auth.log | tail -10
```

## ¿Dónde están los logs?

| Log | Ubicación |
|-----|-----------|
| Hermes Gateway | `~/.hermes/logs/hermes.log` |
| Systemd (gateway) | `sudo journalctl -u hermes-gateway` |
| Backup | `/srv/padrino/logs/backup.log` |
| Restore | `/srv/padrino/logs/restore.log` |
| Security audit | `padrino.db → audit_log table` |
| Code auditor | `~/.hermes_auditor/logs/audit-repo.log` |
| Cron | `sudo grep CRON /var/log/syslog` |
| SSH | `sudo cat /var/log/auth.log` |
