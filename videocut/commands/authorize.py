import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def run_authorization(client_secret_path="client_secret.json", output_path="credentials.json"):
    if os.path.exists(output_path):
        print(f"[✓] {output_path} already exists.")
        return

    if not os.path.exists(client_secret_path):
        print(f"[✗] Missing {client_secret_path}. Download it from Google Cloud Console.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent")

    with open(output_path, "w") as token:
        token.write(creds.to_json())
    print(f"[✓] OAuth complete. Credentials saved to {output_path}")
