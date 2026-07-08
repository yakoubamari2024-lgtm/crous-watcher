import os
import re
import sys
import requests

CROUS_URL = "https://trouverunlogement.lescrous.fr/tools/47/search?bounds=2.9679677_50.6612596_3.125725_50.6008264&locationName=Lille"
FRANCE_URL = "https://trouverunlogement.lescrous.fr/tools/47/search"

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


def get_france_total() -> str:
    try:
        resp = requests.get(FRANCE_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
        match = re.search(r"(\d+)\s+logements?\s+trouvés?\s+en\s+France", html, re.IGNORECASE)
        if match:
            count = match.group(1)
            return f"{count} logement(s) au total en France"
        if "Aucun logement trouvé" in html:
            return "0 logement en France actuellement"
        return "total France indisponible (page inattendue)"
    except Exception as e:
        return f"total France indisponible (erreur: {e})"


def send_france_summary() -> None:
    france_total = get_france_total()
    print(f"Résumé France : {france_total}")
    message = f"📊 Résumé CROUS — {france_total}"
    send_telegram_message(message)


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

    france_total = get_france_total()
    print(f"France: {france_total}")

    if has_listings:
        print("Logement(s) potentiellement disponible(s) à Lille ! Envoi de l'alerte...")
        message = (
            "🏠 Un logement est peut-être disponible sur le CROUS Lille !\n"
            f"{CROUS_URL}\n\n"
            f"📊 {france_total}"
        )
        send_telegram_message(message)
    else:
        print(f"Pas de logement dispo à Lille pour le moment. ({france_total})")


if __name__ == "__main__":
    try:
        if "--france-summary" in sys.argv:
            send_france_summary()
        else:
            check_crous()
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)
