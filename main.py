import os
import time
import json
import base64
import re
import urllib.parse
from typing import List, Optional, Tuple, Dict
from urllib.parse import urlparse

# ---- Gmail imports ----
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# ---- HTML parsing ----
from bs4 import BeautifulSoup

# ---- Playwright ----
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeoutError


# ---- Discord bot ----
from discord_notifier import notify_discord


# =========================
# CONFIG DEFAULTS
# =========================

# Files (change VARIABLES_FILE to your preferred path)
VARIABLES_FILE = os.getenv("VARIABLES_FILE", "data/variables.txt")
CREDENTIALS_JSON_PATH = os.getenv("CREDENTIALS_JSON_PATH", "data/credentials.json")
TOKEN_JSON_PATH = os.getenv("TOKEN_JSON_PATH", "token.json")
COOKIES_JSON_PATH = os.getenv("COOKIES_JSON_PATH", "data/cookies.json")

# Gmail scopes:
# - readonly: read messages
# - modify: (optional) mark processed messages as read
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Polling interval to check Gmail (in seconds)
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "20"))

# =========================
# VARIABLES.TXT LOADER
# =========================

def load_varfile(path: str) -> Dict[str, str]:
    """
    Very simple KEY=VALUE parser. Lines starting with # are ignored.
    Supports \n inside values to represent newlines.
    """
    data: Dict[str, str] = {}
    if not path or not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            v = v.replace("\\n", "\n")
            data[k] = v
    return data

def get_config() -> Dict[str, str]:
    """
    Merge env vars over variables file values.
    """
    file_vars = load_varfile(VARIABLES_FILE)
    cfg = dict(file_vars)
    # env vars override file
    for key in ["EMAIL_FROM", "PREWRITTEN_MESSAGE", "BLOCK_KEYWORDS"]:
        if os.getenv(key):
            cfg[key] = os.getenv(key)
    return cfg

# =========================
# GMAIL HELPERS
# =========================

def load_gmail_credentials() -> Credentials:
    """
    Loads OAuth credentials for Gmail.
    First run: opens a browser for consent and creates token.json.
    Later runs: reuses token.json.
    Supports reading credentials/token from env vars for cloud.
    """
    env_credentials = os.getenv("GMAIL_CREDENTIALS")
    env_token = os.getenv("GMAIL_TOKEN")

    # If both provided via env (cloud)
    if env_credentials and env_token:
        return Credentials.from_authorized_user_info(json.loads(env_token), scopes=GMAIL_SCOPES)

    # Local token.json flow
    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_JSON_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_JSON_PATH, scopes=GMAIL_SCOPES)

    if not creds or not creds.valid:
        # First-time auth
        if env_credentials:
            creds_file = "credentials_tmp.json"
            with open(creds_file, "w", encoding="utf-8") as f:
                f.write(env_credentials)
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
            os.remove(creds_file)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_JSON_PATH, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        # Store locally for next runs
        try:
            with open(TOKEN_JSON_PATH, "w", encoding="utf-8") as token:
                token.write(creds.to_json())
        except Exception:
            pass

    return creds

def get_gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds)

def list_unread_boligportal_messages(service, sender_email: str) -> List[dict]:
    """
    Finds unread messages from BoligPortal. Adjust if needed.
    """
    query = f"from:{sender_email} is:unread newer_than:7d"
    resp = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    return resp.get("messages", []) or []

def fetch_message_html(service, msg_id: str) -> Optional[str]:
    """
    Downloads the message and returns the HTML body (if available).
    """
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    # Look for the HTML part first
    if parts:
        for p in parts:
            if p.get("mimeType") == "text/html":
                data = p.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")

    # Fallback (sometimes only body)
    body_data = payload.get("body", {}).get("data")
    if body_data:
        return base64.urlsafe_b64decode(body_data.encode("utf-8")).decode("utf-8", errors="ignore")

    return None

# =========================
# EMAIL HTML → LINKS
# =========================

def _decode_awstrack_or_google_redirect(href: str) -> str:
    """
    BoligPortal emails often wrap links with tracking, e.g.:
      https://...awstrack.me/L0/https:%2F%2Fwww.boligportal.dk%2F...
    or gmail's https://www.google.com/url?q=<real_url>
    This tries to extract and URL-decode the real boligportal.dk URL.
    """
    # Google redirect
    if href.startswith("https://www.google.com/url?"):
        parsed = urllib.parse.urlparse(href)
        q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
        if q:
            href = q

    # AWS track style ".../L0/<percent-encoded-url>"
    if "/L0/" in href:
        try:
            after = href.split("/L0/", 1)[1]
            # sometimes the encoded URL ends before next /<digit>/...
            # first, percent-decode the whole tail
            decoded = urllib.parse.unquote(after)
            # The decoded may still contain trailing path/ids; strip common /<digits>/ patterns
            # But safest: find first "https://www.boligportal.dk"
            m = re.search(r"https://www\.boligportal\.dk[^\s\"']+", decoded)
            if m:
                href = m.group(0)
        except Exception:
            pass

    return href

def extract_listing_links_from_email_html(html: str) -> List[str]:
    """
    Using your structure:
      <table>
        <tbody>
          <tr> 'Your search' (nested) </tr>
          <tr> (items we want) </tr>   <-- take anchors here
          <tr> 'See all results' (nested) </tr>
    We target tbody > tr:nth-of-type(2) and collect <a> inside (dedupe, normalize).
    """
    soup = BeautifulSoup(html, "html.parser")
    # Pick the first (main) tbody; adjust if multiple
    tbodies = soup.find_all("tbody")
    if not tbodies:
        return []

    # Heuristic: choose the tbody with at least 3 trs (your structure)
    target_tbody = None
    for tb in tbodies:
        trs = tb.find_all("tr", recursive=False)
        if len(trs) >= 3:
            target_tbody = tb
            break
    if not target_tbody:
        # fallback: first tbody
        target_tbody = tbodies[0]

    trs_top = target_tbody.find_all("tr", recursive=False)
    if len(trs_top) < 2:
        return []

    items_tr = trs_top[1]  # the second <tr> with items
    anchors = items_tr.find_all("a", href=True)
    links: List[str] = []

    for a in anchors:
        href = a["href"].strip()
        href = _decode_awstrack_or_google_redirect(href)
        if "boligportal.dk" in href:
            parsed = urlparse(href)
            base_url = f'{parsed.scheme}://{parsed.netloc}{parsed.path}'
            links.append(base_url)

    # De-duplicate preserving order
    seen = set()
    cleaned = []
    for u in links:
        if u not in seen:
            seen.add(u)
            cleaned.append(u)

    return cleaned

# =========================
# PLAYWRIGHT HELPERS
# =========================

def ensure_gmail_token(creds) -> bool:
    """
    Try to refresh the Gmail access token. 
    Returns True if usable, False if refresh failed or creds missing.
    """
    try:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return True
    except Exception as e:
        msg = f"Gmail token refresh failed: {e}"
        print("[Gmail]", msg)
        notify_discord("expired_session", "", extra=msg)
        return False

def load_cookies_into_context(context):
    raw = os.getenv("COOKIES_JSON")
    if not raw:
        with open(COOKIES_JSON_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
    cookies = json.loads(raw)
    for cookie in cookies:
        if "sameSite" in cookie:
            # Normalise unrecognised values
            if cookie["sameSite"] not in ("Strict", "Lax", "None"):
                # Choose a sensible default; Lax is usually fine
                cookie["sameSite"] = "Lax"
    context.add_cookies(cookies)

def cookies_are_valid(page) -> bool:
    pageContent = page.content().lower()
    return ("log ind" not in pageContent)

def page_contains_block_keywords(page: Page, keywords_csv: str) -> Tuple[bool, Optional[str]]:
    """
    Returns True if any keyword from BLOCK_KEYWORDS appears in the
    text of a <div class="css-o9y6d5"> element. If no such divs are found,
    or none contain the keywords, returns False.
    """
    if not keywords_csv.strip():
        return False, None

    # Normalise the keywords once
    keywords = [kw.strip().lower() for kw in keywords_csv.split(",") if kw.strip()]
    if not keywords:
        return False, None

    try:
        # Get all inner texts of the target divs at once
        texts = page.locator("div.css-o9y6d5").all_inner_texts()
    except Exception:
        # If selector fails or no elements, treat as empty list
        texts = []

    # Combine and lower‑case the text from all matching divs
    combined_text = " ".join(t.lower() for t in texts)

    # Check each keyword against the combined text
    for kw in keywords:
        if kw in combined_text:
            return True, kw
    return False, None

def already_contacted_redirect(url: str) -> bool:
    """
    If URL contains 'indbakke', assume it's your inbox (already contacted).
    """
    return "indbakke" in url.lower() or "inbox" in url.lower()

def click_contact_and_send(page: Page, message_text: str) -> bool:
    """
    1) Click 'Contact' button
    2) If redirected to 'indbakke' (already contacted) -> stop
    3) Else handle dialog:
       - find textarea (id='__TextField1' or any textarea)
       - fill message
       - click 'Send'
    """

    # Extract listing info (title and address) for notifications
    advertTitle, advertAddress = extract_listing_info(page)

    # Click the "Contact" button (be flexible with text)
    # Try multiple strategies
    contact_clicked = False
    selectors_try = [
        # by role & text
        lambda: page.get_by_role("button", name=re.compile(r"(Contact|Kontakt)", re.I)).click(timeout=5000),
        # by text inside span
        lambda: page.locator("button:has-text('Skriv til udlejer')").first.click(timeout=5000),
        lambda: page.locator("button:has-text('Contact')").first.click(timeout=5000),
        lambda: page.locator("button:has-text('Kontakt')").first.click(timeout=5000),
        # class heuristic (your sample)
        lambda: page.locator("button.temporaryButtonClassname").first.click(timeout=5000),
    ]
    for fn in selectors_try:
        try:
            fn()
            contact_clicked = True
            break
        except Exception:
            continue

    if not contact_clicked:
        print("[Playwright] Could not find the Contact button.")
        return False

    # Small wait to allow any navigation or dialog
    page.wait_for_timeout(800)

    # If navigation happened and URL contains 'indbakke' -> already contacted
    current_url = page.url
    if already_contacted_redirect(current_url):
        print("[Playwright] Landed on inbox (indbakke) — already contacted earlier. Skipping.")
        notify_discord("already", current_url, f"{advertTitle} | {advertAddress}")
        return True  # treat as 'done'

    # If a dialog pops up
    # Try to locate the dialog, textarea, and Send button
    try:
        # Look for a visible textarea
        textarea = None
        try:
            textarea = page.locator("textarea#\\__TextField1").first
            if not textarea.is_visible():
                textarea = None
        except Exception:
            textarea = None

        if textarea is None:
            # Any textarea inside an open dialog
            # Radix dialogs usually have role="dialog"
            textarea = page.locator("div[role='dialog'] textarea").first
            if not textarea or not textarea.is_visible():
                # fallback: any textarea on page
                textarea = page.locator("textarea").first

        textarea.click(timeout=5000)
        textarea.fill(message_text, timeout=8000)

        # Click Send (text 'Send')
        sent = False
        try_send = [
            lambda: page.get_by_role("button", name=re.compile(r"^Send$", re.I)).click(timeout=5000),
            lambda: page.locator("div[role='dialog'] button:has-text('Send')").first.click(timeout=5000),
            lambda: page.locator("button:has-text('Send')").first.click(timeout=5000),
        ]
        for fn in try_send:
            try:
                fn()
                sent = True
                notify_discord("sent", page.url,  f"{advertTitle} | {advertAddress}")
                break
            except Exception:
                continue

        if not sent:
            print("[Playwright] Could not find the Send button.")
            notify_discord("failed", page.url, "Could not find the Send button")
            return False

        # # tiny wait for any toast/confirmation
        page.wait_for_timeout(1200)
        return True

    except Exception as e:
        print(f"[Playwright] Dialog handling failed: {e}")
        notify_discord("failed", page.url, f"Dialog handling failed: {e}")
        return False


def extract_listing_info(page: Page):
    """
    Returns (titleText, addressText)
      - titleText: listing title (e.g., "1 room apartment of 38 m²")
      - addressText: text of the matching address div sliced from the first 4-digit ZIP; or None
    """
    # 1) Title: prefer the exact class you provided
    titleText = None
    print(f"[Playwright] PAGE.{page.url}")
    loc = page.locator("span.css-v34a4n").first
    try:
        # Wait for it to be visible and read it
        loc.wait_for(state="visible", timeout=5000)
        titleText = loc.inner_text().strip()
    except PWTimeoutError:
        # 2) Minimal fallback: any span that contains "m²"
        # (keeps things robust across minor class/name changes)
        alt = page.locator("span", has_text=re.compile(r"\bm²\b")).first
        try:
            alt.wait_for(state="attached", timeout=3000)
            candidate = (alt.text_content() or "").strip()
            if candidate:
                titleText = candidate
        except PWTimeoutError:
            pass

    if not titleText:
        # If absolutely nothing matched, return None for title (and address later)
        titleText = None

    # 3) Address: find the first div.css-o9y6d5 containing a 4-digit ZIP, then slice from ZIP → end
    addressText = None
    addressDivs = page.locator("div.css-o9y6d5")

    try:
        count = addressDivs.count()  # number of matching divs (may be 0)
        for i in range(count):
            text = (addressDivs.nth(i).inner_text() or "").strip()
            m = re.search(r"\b\d{4}\b", text)
            if m:
                addressText = text[m.start():].strip()
                break
    except PWTimeoutError:
        # If count() or inner_text() times out (rare), leave addressText as None
        pass

    return titleText, addressText


def process_listing(url: str, message_text: str, block_keywords: str) -> bool:
    """
    Open listing, check block keywords, then send message if allowed.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # set False to debug locally
        context = browser.new_context()
        load_cookies_into_context(context)
        page = context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=60000)
            
            if not cookies_are_valid(page):
                print("[Playwright] Cookies are invalid or expired. Cannot proceed.")
                notify_discord("expired_session", url, "Failed to login. Cookies are invalid or expired")
                return False


            # Block keywords check
            foundBlockedKeyword, keyword = page_contains_block_keywords(page, block_keywords) 
            if foundBlockedKeyword:
                print(f"[Playwright] Block keyword matched '{keyword}' — skipping this listing.")
                notify_discord("blocked", url, f"{keyword}")
                return True  # treat skip as handled

            # Try to contact
            ok = click_contact_and_send(page, message_text)
            return ok
        except Exception as e:
            print(f"[Playwright] Failed on {url}: {e}")
            return False
        finally:
            browser.close()

# =========================
# MAIN EMAIL → LISTING LOOP
# =========================

def extract_listing_links_from_message_html(html: str) -> List[str]:
    """
    Wrapper to hook in your layout-specific extraction.
    """
    return extract_listing_links_from_email_html(html)

def process_new_emails_once(service, sender_email: str, message_text: str, block_keywords: str) -> None:
    try:
        msgs = list_unread_boligportal_messages(service, sender_email)
        if not msgs:
            print(f"[Bot] No emails found.")
            return

        print(f"[Bot] Found {len(msgs)} emails.")
        for m in msgs:
            msg_id = m["id"]
            html = fetch_message_html(service, msg_id)
            if not html:
                continue

            links = extract_listing_links_from_message_html(html)
            if not links:
                continue

            print(f"[Bot] Found {len(links)} link(s) in email.")
            for url in links:
                if "boligportal.dk" not in url:
                    continue
                print(f"[Bot] Processing listing: {url}")
                ok = process_listing(url, message_text, block_keywords)
                # print(f"[Bot] Result: {'SENT/OK' if ok else 'FAILED'}")

            # OPTIONAL: mark as read (requires gmail.modify scope)
            # service.users().messages().modify(
            #     userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            # ).execute()
            service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()

    except HttpError as he:
        print(f"[Gmail] API error: {he}")
    except Exception as e:
        print(f"[Bot] Unexpected error: {e}")

def main():
    cfg = get_config()
    sender = cfg["EMAIL_FROM"]
    message_text = cfg["PREWRITTEN_MESSAGE"]
    block_keywords = cfg.get("BLOCK_KEYWORDS", "")

    print("Starting Gmail → BoligPortal bot…")
    print(f"- Waiting for emails from: {sender}")
    creds = load_gmail_credentials()
    service = get_gmail_service(creds)

    while True:
        if not ensure_gmail_token(creds):
            break
        try:
            process_new_emails_once(service, sender, message_text, block_keywords)
        except HttpError as he:
            # If unauthorized, notify + stop so you can re-auth
            status = getattr(he, "status_code", None)
            if status == 401:
                msg = "Gmail 401 Unauthorized: delete token.json and re-authorize."
                print("[Gmail]", msg)
                notify_discord("expired_session", "", extra=msg)
                break
            else:
                print(f"[Gmail] API error: {he}")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
