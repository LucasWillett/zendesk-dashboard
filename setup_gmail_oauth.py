#!/usr/bin/env python3
"""
One-time setup script to get Gmail OAuth refresh token.
Run this locally, then add the refresh token to GitHub Secrets.
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Gmail API scope - read-only access to emails
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    print("=== Gmail OAuth Setup ===\n")

    # Check for credentials file
    if not os.path.exists('credentials.json'):
        print("ERROR: credentials.json not found!")
        print("Create it with your OAuth client ID and secret.")
        return

    # Check if client_secret is set
    with open('credentials.json') as f:
        creds_data = json.load(f)
        if 'PASTE' in creds_data['installed'].get('client_secret', ''):
            print("ERROR: You need to paste your client_secret in credentials.json")
            print("Get it from Google Cloud Console → Credentials → Your OAuth client")
            return

    print("Starting OAuth flow...")
    print("A browser window will open - sign in with lucas@visitingmedia.com\n")

    # Run the OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8080)

    print("\n=== SUCCESS ===\n")
    print("Add these as GitHub Secrets:\n")
    print(f"GMAIL_CLIENT_ID: {creds_data['installed']['client_id']}")
    print(f"GMAIL_CLIENT_SECRET: {creds_data['installed']['client_secret']}")
    print(f"GMAIL_REFRESH_TOKEN: {creds.refresh_token}")

    # Also save token locally for testing
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    with open('token.json', 'w') as f:
        json.dump(token_data, f, indent=2)

    print("\nToken also saved to token.json for local testing.")
    print("\nIMPORTANT: Don't commit credentials.json or token.json to git!")


if __name__ == '__main__':
    main()
