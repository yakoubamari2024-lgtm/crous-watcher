import os
import re
import sys
import requests

CROUS_URL = "https://trouverunlogement.lescrous.fr/tools/47/search?bounds=2.9679677_50.6612596_3.125725_50.6008264&locationName=Lille"

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


def check_crous() -> None:
    resp = requests.get(CROUS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
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

    if has_listings:
        print("Logement(s) potentiellement disponible(s) ! Envoi de l'alerte...")
        message = (
            "🏠 Un logement est peut-être disponible sur le CROUS Lille !\n"
            f"{CROUS_URL}"
        )
        send_telegram_message(message)
    else:
        print("Pas de logement dispo pour le moment.")


if __name__ == "__main__":
    try:
        check_crous()
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)
