# discord_notifier.py
import os
import requests

# Load variables from file
def load_variables(path="data/variables.txt"):
    variables = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    variables[key] = value
    return variables

def get_webhook_url():
    # Prefer environment variable, fallback to variables.txt
    env_url = os.getenv("DISCORD_WEBHOOK_URL")
    if env_url and env_url.strip():
        return env_url.strip()
    vars_file = load_variables()
    file_url = vars_file.get("DISCORD_WEBHOOK_URL", "").strip()
    return file_url if file_url else None

WEBHOOK_URL = get_webhook_url()

def notify_discord(event_type: str, listing_url: str, extra: str = ""):
    if not WEBHOOK_URL:
        print("[Discord] No webhook URL found, skipping notification.")
        return False

    # Map events to readable messages with emojis
    messages = {
        "blocked": f"🚫 **Blocked keyword** '{extra}'\n🔗 {listing_url}\n\u200B",
        "sent":    f"✅ **Message sent**\n{extra}\n🔗 {listing_url}\n\u200B",
        "already": f"ℹ️ **Already contacted**\n{extra}\n🔗 {listing_url}\n\u200B",
        "failed":  f"⚠️ **Failed to send** – {extra}\n🔗 {listing_url}\n\u200B",
        "expired_session": f"❌ **Invalid session**\ - {extra}\n\u200B",
    }

    if event_type not in messages:
       print(f"[Discord] Unknown event type '{event_type}', skipping notification.")
       return False

    content = messages[event_type]

    try:
        response = requests.post(WEBHOOK_URL, json={"content": content})
        if response.status_code == 204:
            print(f"[Discord] Notification sent: {event_type}")
            return True
        else:
            print(f"[Discord] Failed to send ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"[Discord] Error sending message: {e}")
        return False
