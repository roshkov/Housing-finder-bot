# Housing finder bot

This project demonstrates how the process of handling property rentals can be automated. It checks for new rental listing emails, opens the rental website in a browser, and sends a predefined message to the landlord through the site’s internal messaging system. In addition, the activity is logged to a Discord channel, and the setup can be deployed on Railway.

## Disclaimer
This code is created and used strictly for programming practice and educational purposes only; it is never deployed or used to contact landlords on the website. As such, it serves solely as a technical demonstration. The script does not violate the website’s Terms and Conditions because it relies only on the user’s own login, performs permitted actions within the platform (viewing rentables and sending messages through the internal system), does not share or transfer access (§1.2), does not bypass payment or subscription terms (§1.3), and does not solicit off-platform communication or process sensitive personal data (§1.5.2). It remains fully within the scope of seeker use for personal accommodation search (§2.1–2.2).

---

## Stack
- **Python** – main language for the script  
- **Gmail API** – read emails when the portal sends new listings  
- **Playwright** – browser automation (sending messages to landlords on the website)  
- **Railway** – cloud hosting  

---

## Setup

### Gmail API
1. Create a project on [Google Cloud Console](https://console.cloud.google.com/).  
2. Enable **Gmail API**.  
3. Create **OAuth credentials**.  
4. Store the credentials.  
5. Under **APIs & Services → OAuth consent screen**:  
   - Add yourself as a Test User in the **Audience** tab.  
   - Add the `auth/gmail.readonly`, `auth/gmail.modify` scope in the **Data Access** tab.
  
### Switch Google OAuth App from Testing → Production

1. Go to [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent) in Google Cloud Console. Select the project
2. Scroll to **Publishing status** → click **Publish app**.  
3. Get Gmail Token for Railway (see below)
4. Running main.py will create data/token.json
5. Add it as environmetnal variable for railway (if running in railway)

### Cookies from Website
1. Install the **Cookie-Editor** extension for Chrome.  
2. Export cookies as `cookies.json`.  
3. Save it in the `/data` folder.  


### Python Dependencies
```bash
pip install -r requirements.txt
playwright install   # downloads the actual browsers used by Playwright
```

### Setup Discord Bot
There is only simple logging required; messages are sent using `requests` to a Discord webhook.

1. In Discord: **Edit Channel → Integrations → Webhooks → New Webhook**. Copy the webhook URL.  
2. Add the URL into `variables.txt`:  

   ```env
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXX/YYY

### Setup Railway

1. Generate your Gmail token locally (see below).  
2. Collect the secrets that will be inserted as Railway variables.  
3. Add a `Dockerfile`.  
4. Create a Railway project:  
   - Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub** → pick your repo.  
5. Add environment variables:  

   ```env
   GMAIL_TOKEN=...
   COOKIES_JSON=...
   DISCORD_WEBHOOK_URL=...
   EMAIL_FROM=...
   PREWRITTEN_MESSAGE=...
   BLOCK_KEYWORDS=...
   POLL_SECONDS=...

Do not add Gmail credentials directly.

### Get Gmail Token for Railway
1. Run the script python
   ```env
   python get_gmail_token.py
2. Sign in when the browser opens.
3. Copy the entire JSON the script prints (it must include "refresh_token").
4. Add it to Railway variables as GMAIL_TOKEN_JSON.
