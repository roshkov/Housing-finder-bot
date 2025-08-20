

import os
import tempfile
import pytest
from unittest import mock

import discord_notifier

def test_load_variables_reads_key_value_pairs(tmp_path):
    # Create a temporary variables.txt file
    content = "DISCORD_WEBHOOK_URL=https://example.com/webhook\nFOO=bar"
    varfile = tmp_path / "variables.txt"
    varfile.write_text(content, encoding="utf-8")

    result = discord_notifier.load_variables(str(varfile))
    assert result["DISCORD_WEBHOOK_URL"] == "https://example.com/webhook"
    assert result["FOO"] == "bar"

def test_get_webhook_url_prefers_env(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://env-url")
    with mock.patch("discord_notifier.load_variables", return_value={"DISCORD_WEBHOOK_URL": "https://file-url"}):
        url = discord_notifier.get_webhook_url()
        assert url == "https://env-url"

def test_get_webhook_url_fallback_to_file(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    with mock.patch("discord_notifier.load_variables", return_value={"DISCORD_WEBHOOK_URL": "https://file-url"}):
        url = discord_notifier.get_webhook_url()
        assert url == "https://file-url"

def test_get_webhook_url_none_if_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    with mock.patch("discord_notifier.load_variables", return_value={}):
        url = discord_notifier.get_webhook_url()
        assert url is None

@mock.patch("discord_notifier.requests.post")
def test_notify_discord_success(mock_post, monkeypatch):
    # Patch WEBHOOK_URL to a dummy value
    monkeypatch.setattr(discord_notifier, "WEBHOOK_URL", "https://dummy")
    mock_post.return_value.status_code = 204

    result = discord_notifier.notify_discord("sent", "http://listing", "extra info")
    assert result is True
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["content"].startswith("✅")

@mock.patch("discord_notifier.requests.post")
def test_notify_discord_failure_status(mock_post, monkeypatch):
    monkeypatch.setattr(discord_notifier, "WEBHOOK_URL", "https://dummy")
    mock_post.return_value.status_code = 400
    mock_post.return_value.text = "Bad Request"

    result = discord_notifier.notify_discord("sent", "http://listing", "extra info")
    assert result is False

def test_notify_discord_no_webhook(monkeypatch):
    monkeypatch.setattr(discord_notifier, "WEBHOOK_URL", None)
    result = discord_notifier.notify_discord("sent", "http://listing", "extra info")
    assert result is False

@mock.patch("discord_notifier.requests.post", side_effect=Exception("Network error"))
def test_notify_discord_exception(mock_post, monkeypatch):
    monkeypatch.setattr(discord_notifier, "WEBHOOK_URL", "https://dummy")
    result = discord_notifier.notify_discord("sent", "http://listing", "extra info")
    assert result is False


# Insert the real webhook URL for testing
# def test_notify_discord_real_webhook():
#     webhookURL = "https://WEBHOOK_URL"
#     discord_notifier.WEBHOOK_URL = webhookURL

#     test_url = "https://test.com/listing/123"
#     results = []
#     results.append(discord_notifier.notify_discord("blocked", test_url, "blocked keyword"))
#     results.append(discord_notifier.notify_discord("sent", test_url, "title | address"))
#     results.append(discord_notifier.notify_discord("already", test_url, "title | address"))
#     results.append(discord_notifier.notify_discord("failed", test_url, extra="error message"))
#     results.append(discord_notifier.notify_discord("expired_session", "", extra="session expired"))
    
#     results.append(discord_notifier.notify_discord("unknown", test_url, "something else"))

#     assert all(r is True for r in results[:-1])
#     assert results[-1] is False