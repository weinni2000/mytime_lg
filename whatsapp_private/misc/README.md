# Private WhatsApp sender

This command sends a text message through a private WhatsApp account using Neonize and
WhatsApp's unofficial multi-device protocol.

## Install

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Send a message

Use the recipient's international number including the country code:

```bash
.venv/bin/python send_whatsapp.py +436641234567 \
  --message "Hello from Python"
```

For a longer message:

```bash
.venv/bin/python send_whatsapp.py +436641234567 \
  --message-file message.txt
```

On the first run, scan the displayed QR code in WhatsApp under **Linked devices**. The
local `whatsapp_session.db` file keeps the login for later runs. Do not commit or share
that file.

## Important

Neonize is not an official Meta/WhatsApp API. Protocol changes may break the integration
and automated use may lead to account restrictions. Send only expected messages to
recipients who have consented; do not use it for spam or bulk messaging. For
business-critical messaging, use Meta's official WhatsApp Cloud API instead.
