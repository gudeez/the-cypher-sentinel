import requests
from config import TG_BOT_TOKEN, TG_CHANNEL_ID

SITE_URL = "https://cyphersentinel.up.railway.app/"


def send_edition_to_telegram(digest_text, edition_date):
    """Send a brief notification with link to the configured Telegram channel."""
    if not TG_BOT_TOKEN or not TG_CHANNEL_ID:
        print("[Telegram] No bot token or channel ID configured, skipping")
        return False

    message = (
        f"🛡 *THE CYPHER SENTINEL*\n"
        f"_{edition_date}_\n\n"
        f"{digest_text}\n\n"
        f"📰 [Read the full edition]({SITE_URL})"
    )

    # Keep it well under Telegram's 4096 char limit
    if len(message) > 1500:
        message = message[:1450] + f"...\n\n📰 [Read the full edition]({SITE_URL})"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHANNEL_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        data = resp.json()
        if data.get("ok"):
            print(f"[Telegram] Sent to {TG_CHANNEL_ID}")
            return True
        else:
            print(f"[Telegram] API error: {data.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"[Telegram] Failed to send: {e}")
        return False
