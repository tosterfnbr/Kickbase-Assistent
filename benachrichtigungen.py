import getpass
import json
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import keyring

APP = "KickbaseAssistent"
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"

config = json.loads(CONFIG.read_text(encoding="utf-8"))
print("\nE-Mail-Benachrichtigungen einrichten")
print("Bei Gmail wird ein 16-stelliges Google-App-Passwort benötigt, nicht das normale Passwort.\n")
recipient = input("Empfänger-E-Mail: ").strip()
username = input(f"Absender/SMTP-Benutzer [{recipient}]: ").strip() or recipient
host = input("SMTP-Server [smtp.gmail.com]: ").strip() or "smtp.gmail.com"
port = int(input("SMTP-Port [465]: ").strip() or "465")
show_password = input("E-Mail-App-Passwort beim Tippen anzeigen? (J/N) [N]: ").strip().casefold() in ("j", "ja", "y", "yes")
password = (
    input("E-Mail-App-Passwort (sichtbar): ")
    if show_password
    else getpass.getpass("E-Mail-App-Passwort (bleibt unsichtbar): ")
).replace(" ", "")
x_token = getpass.getpass("Optionaler X-API-Bearer-Token [Enter = X aus]: ").strip()

if not recipient or not username or not password:
    raise SystemExit("Einrichtung abgebrochen: Angaben unvollständig.")

message = EmailMessage()
message["Subject"] = "KICKBASE Assistent – Test erfolgreich"
message["From"] = username
message["To"] = recipient
message.set_content("Die E-Mail-Benachrichtigungen deines KICKBASE Assistenten funktionieren.")

with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
    server.login(username, password)
    server.send_message(message)

keyring.set_password(APP, "smtp_password", password)
if x_token:
    keyring.set_password(APP, "x_bearer_token", x_token)
config.update({
    "email_notifications": True,
    "notification_email": recipient,
    "smtp_username": username,
    "smtp_host": host,
    "smtp_port": port,
    "news_monitor": True,
    "news_poll_minutes": 60,
    "x_monitor": bool(x_token),
})
CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
print("\nTest-E-Mail wurde gesendet. Benachrichtigungen sind aktiv.")