import json
import os
import re
import sys
import time
import requests

CROUS_URL = "https://trouverunlogement.lescrous.fr/tools/47/search?bounds=2.9679677_50.6612596_3.125725_50.6008264&locationName=Lille"
FRANCE_URL = "https://trouverunlogement.lescrous.fr/tools/47/search"

FRANCE_STATE_FILE = "france_count.txt"
LILLE_STATE_FILE = "lille_state.json"
STATUS_INTERVAL_SECONDS = 10 * 60  # 10 minutes

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=20)
    resp.raise_for_status()


def get_france_count():
    try:
        resp = requests.get(FRANCE_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        html = resp.text

        match = re.search(r"(\d+)\s+logements?\s+trouvés?\s+en\s+France", html, re.IGNORECASE)
        if match:
            return int(match.group(1))

        if "Aucun logement trouvé" in html:
            return 0

        return None
    except Exception as e:
        print(f"Erreur en récupérant le total France : {e}")
        return None


def read_previous_france_count():
    if not os.path.exists(FRANCE_STATE_FILE):
        return None
    try:
        with open(FRANCE_STATE_FILE, "r") as f:
            content = f.read().strip()
            return int(content) if content else None
    except Exception:
        return None


def write_current_france_count(count: int) -> None:
    with open(FRANCE_STATE_FILE, "w") as f:
        f.write(str(count))


def send_france_summary() -> None:
    current = get_france_count()
    if current is None:
        print("Impossible de déterminer le total France pour le moment, pas d'alerte.")
        return

    previous = read_previous_france_count()
    print(f"Total France actuel: {current}, précédent connu: {previous}")

    if previous is None:
        print("Premier relevé, on enregistre sans notifier.")
        write_current_france_count(current)
        return

    if current != previous:
        direction = "📈 en hausse" if current > previous else "📉 en baisse"
        message = (
            f"📊 Le nombre de logements en France a changé ({direction}) !\n"
            f"Avant : {previous} → Maintenant : {current}"
        )
        send_telegram_message(message)
        write_current_france_count(current)
    else:
        print("Pas de changement, aucune alerte envoyée.")


def read_lille_state() -> dict:
    if not os.path.exists(LILLE_STATE_FILE):
        return {"last_alert": None, "last_status": None}
    try:
        with open(LILLE_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_alert": None, "last_status": None}


def write_lille_state(state: dict) -> None:
    with open(LILLE_STATE_FILE, "w") as f:
        json.dump(state, f)


def check_crous() -> None:
    resp = requests.get(CROUS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    html = resp.text

    print(f"Status code: {resp.status_code}, taille de la page: {len(html)} caractères")

    no_results = "Aucun logement trouvé" in html
    is_real_page = "Trouver un logement" in html or "trouverunlogement" in html.lower()

    match = re.search(r"page\s+(\d+)\s+sur\s+(\d+)", html, re.IGNORECASE)
    total_pages = int(match.group(2)) if match else None

    print(f"is_real_page={is_real_page}, no_results_text={no_results}, total_pages={total_pages}")

    if not is_real_page:
        print("La page reçue ne ressemble pas à la vraie page CROUS (blocage/anti-bot ?). Pas d'alerte envoyée, à surveiller.")
        return

    has_listings = (not no_results) and (total_pages is None or total_pages > 0)

    now = int(time.time())
    state = read_lille_state()
    heure = time.strftime("%H:%M", time.gmtime(now + 2 * 3600))

    if has_listings:
        last_alert = state.get("last_alert")
        if last_alert is None or (now - last_alert) >= STATUS_INTERVAL_SECONDS:
            print("Logement disponible à Lille ! Envoi de 5 notifications...")
            france_count = get_france_count()
            france_text = f"{france_count} logement(s) au total en France" if france_count is not None else "total France indisponible"
            message = (
                "🏠🏠🏠 UN LOGEMENT EST DISPONIBLE SUR LE CROUS LILLE ! 🏠🏠🏠\n"
                f"{CROUS_URL}\n\n"
                f"📊 {france_text}\n"
                f"⏰ {heure}"
            )
            for _ in range(5):
                send_telegram_message(message)
            state["last_alert"] = now
            write_lille_state(state)
        else:
            restant = STATUS_INTERVAL_SECONDS - (now - last_alert)
            print(f"Déjà alerté récemment, prochaine relance possible dans {restant}s.")
    else:
        last_status = state.get("last_status")
        if last_status is None or (now - last_status) >= STATUS_INTERVAL_SECONDS:
            print("Pas de logement à Lille, envoi du message de statut.")
            message = f"❌ Toujours aucun logement dispo à Lille pour le moment. (vérifié à {heure})"
            send_telegram_message(message)
            state["last_status"] = now
            write_lille_state(state)
        else:
            print("Pas de logement, mais message de statut déjà envoyé il y a moins de 10 min.")


if __name__ == "__main__":
    try:
        if "--france-summary" in sys.argv:
            send_france_summary()
        else:
            check_crous()
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)
