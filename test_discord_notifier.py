from discord_notifier import notify_discord

# Replace with any URL you want for testing
test_url = "https://example.com/listing/123"

print("Testing Discord notifications...")

notify_discord("blocked", test_url, "blocked keyword")
notify_discord("sent", test_url, "title | address")
notify_discord("already", test_url, "title | address")
notify_discord("failed", test_url, extra="error message")