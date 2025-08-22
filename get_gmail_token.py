from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # <-- adjust if needed

def main():
    # Load OAuth credentials (from Google cloud console)
    flow = InstalledAppFlow.from_client_secrets_file(
        "data/credentials.json", SCOPES
    )
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print(creds.to_json())

if __name__ == "__main__":
    main()