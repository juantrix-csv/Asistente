# Telegram Setup — Padrino Digital

Cómo crear y configurar el bot de Telegram para Padrino Digital.

## 1. Crear el Bot con @BotFather

1. Abrí Telegram y buscá `@BotFather` (el bot oficial de Telegram para crear bots)
2. Enviá el comando `/newbot`
3. BotFather te va a preguntar:
   - **Nombre del bot**: Elegí un nombre visible (ej. "Padrino Digital")
   - **Username del bot**: Debe terminar en `bot` (ej. `PadrinoDigitalBot`)
4. BotFather te va a dar un **token** — GUARDALO. Es lo único que necesitás para
   que Padrino se conecte a Telegram.

```
Done! Congratulations on your new bot. You will find it at t.me/PadrinoDigitalBot.

Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890

Keep your token secure and store it safely, it can be used by anyone to control your bot.
```

## 2. Configurar Privacidad del Bot

Por seguridad, el bot NO debe leer todos los mensajes del grupo — solo los
que empiezan con comandos o lo mencionan.

En @BotFather:
1. `/setprivacy`
2. Seleccioná tu bot
3. Elegí **Enable**

## 3. Configurar Comandos del Bot

En @BotFather:
1. `/setcommands`
2. Seleccioná tu bot
3. Pegá esta lista:

```
hoy - Plan del día
plan - Planificación completa
tareas - Ver tareas pendientes
inbox - Clasificar un mensaje o idea
gasto - Registrar un gasto (monto + descripción)
ingreso - Registrar un ingreso
finanzas - Resumen financiero
presupuesto - Ver estado de presupuestos
ahorro - Ver metas de ahorro
deudas - Ver deudas
habito - Registrar un hábito completado
modo - Cambiar modo (normal, firme, crisis, enfoque, finanzas)
checkin - Check-in diario (energía + horas disponibles)
resumen - Revisión del día
recordar - Guardar algo en la memoria
backup - Hacer un backup manual
restaurar - Restaurar desde un backup
auditar - Auditar un repositorio de código
ayuda - Mostrar esta ayuda
```

Estos comandos aparecen como sugerencias cuando el usuario escribe `/` en el chat.

## 4. Configurar Webhook

Padrino Digital usa webhooks (no polling) para recibir mensajes de Telegram.
El webhook le dice a Telegram a qué URL enviar los mensajes.

```bash
# Reemplazá <TOKEN> con tu token y <VPS_IP_OR_DOMAIN> con la IP/dominio de tu VPS
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<VPS_IP_OR_DOMAIN>:8443/telegram"}'
```

Respuesta esperada:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

### Verificar el webhook

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Debe mostrar `"url": "https://..."` y `"has_custom_certificate": false`.

### Si usás ngrok (desarrollo local)

```bash
# En una terminal
ngrok http 8443

# En otra terminal (reemplazá <NGROK_URL> con la URL que te da ngrok)
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<NGROK_URL>/telegram"
```

## 5. Configurar el Token en Padrino

Agregá el token a `~/.hermes/.env`:

```bash
nano ~/.hermes/.env
```

```bash
HERMES_TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
```

**IMPORTANTE**: Asegurate de que el archivo tenga permisos 600:
```bash
chmod 600 ~/.hermes/.env
```

## 6. Firewall — Abrir el Puerto del Gateway

Si tu VPS tiene firewall (UFW, configurado por `setup.sh`), asegurate que el
puerto del gateway esté abierto:

```bash
sudo ufw allow 8443/tcp
sudo ufw status
```

## 7. HTTPS (Recomendado para producción)

Telegram requiere HTTPS para webhooks en producción. Opciones:

### Con Let's Encrypt (gratis)

```bash
# Instalar certbot
sudo apt install certbot

# Si ya tenés nginx
sudo certbot --nginx -d tu-dominio.com

# O standalone (sin nginx)
sudo certbot certonly --standalone -d tu-dominio.com
```

### Con IP directa + certificado autofirmado

Para desarrollo/testing, podés usar un certificado autofirmado:

```bash
openssl req -newkey rsa:2048 -sha256 -nodes \
  -keyout /home/padrino/hermes-agent/certs/private.key \
  -x509 -days 365 \
  -out /home/padrino/hermes-agent/certs/cert.pem \
  -subj "/C=AR/ST=BuenosAires/L=City/O=Padrino/CN=TU_VPS_IP"
```

Luego subí el certificado a Telegram:
```bash
curl -F "url=https://<VPS_IP>:8443/telegram" \
     -F "certificate=@/home/padrino/hermes-agent/certs/cert.pem" \
     "https://api.telegram.org/bot<TOKEN>/setWebhook"
```

## 8. Probar el Bot

Abrí Telegram, buscá tu bot por el username, y enviá:

```
Hola
```

Si todo está bien, Padrino debería responder.

### Troubleshooting rápido

| Problema | Verificar |
|----------|-----------|
| No responde | `systemctl status hermes-gateway` |
| Error 401 | Token incorrecto en `.env` |
| Error webhook | `curl .../getWebhookInfo` — ¿URL correcta? |
| Error SSL | ¿HTTPS configurado? ¿Puerto abierto en firewall? |
| Timeout | ¿El VPS es accesible desde internet? |

Ver [TROUBLESHOOTING.md](TROUBLESHOOTING.md) para más detalles.

## 9. Personalizar el Bot (opcional)

En @BotFather podés configurar:

- `/setdescription` — Descripción del bot
- `/setabouttext` — Texto "Acerca de"
- `/setuserpic` — Foto de perfil del bot
- `/setname` — Cambiar nombre

Ejemplo de descripción:
```
Padrino Digital — Tu asistente personal.
Organizo tus tareas, finanzas, disciplina y proyectos.
Vivo en tu VPS, no comparto tus datos.
Comandos: /ayuda
```
