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

VARS = load_variables()
WEBHOOK_URL = VARS.get("DISCORD_WEBHOOK_URL")

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
    }

    content = messages.get(event_type, f"ℹ️ **Notification**\n🔗 {listing_url}")

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
