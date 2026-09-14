import getpass
import json
from pathlib import Path
import keyring

APP = "KickbaseAssistent"
ROOT = Path(__file__).resolve().parent

print("\nDie Zugangsdaten werden im Windows-Anmeldedatenspeicher abgelegt.")
email = input("KICKBASE-E-Mail: ").strip()
show_password = input("KICKBASE-Passwort beim Tippen anzeigen? (J/N) [N]: ").strip().casefold() in ("j", "ja", "y", "yes")
password = input("KICKBASE-Passwort (sichtbar): ") if show_password else getpass.getpass("KICKBASE-Passwort (bleibt unsichtbar): ")
league = input("LigName [Bierbanausen]: ").strip() or "Bierbanausen"

if not email or not password:
    raise SystemExit("E-Mail und Passwort dürfen nicht leer sein.")

keyring.set_password(APP, "email", email)
keyring.set_password(APP, "password", password)

config = {
    "league_name": league,
    "poll_minutes": 5,
    "mode": "observe",
    "minimum_cash": 1000000,
    "maximum_overpay_percent": 8,
    "trading_enabled": False,
    "auto_buy": True,
    "auto_instant_sell": True,
    "auto_accept_offers": True,
    "auto_adjust_listings": True,
    "minimum_squad_size": 11,
    "max_actions_per_run": 1,
    "matchday_protection_hours": 48,
    "bid_window_minutes": 10,
    "continuous_bidding": True,
    "bid_refresh_minutes": 30,
    "player_details_refresh_minutes": 60,
    "minimum_starting_probability": 3,
    "asking_price_percent": 2,
    "protected_players": [],
    "targets": [],
    "watchlist_names": [],
    "email_notifications": False,
    "notification_email": "",
    "smtp_username": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "news_monitor": True,
    "news_poll_minutes": 60,
    "news_max_age_hours": 72,
    "risk_news_hours": 36,
    "x_monitor": False
}
(ROOT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
print("Einrichtung gespeichert. Echte Transfers können anschließend im Dashboard einmalig freigeschaltet werden.")