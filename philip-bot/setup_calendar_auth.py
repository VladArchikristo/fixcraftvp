#!/usr/bin/env python3
"""
One-time OAuth setup for Google Calendar API.
Run this script once to authorize and save token.pickle
"""
import os
import pickle
import warnings
warnings.filterwarnings('ignore')

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'token.pickle')

def main():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # Use console flow - prints URL that user visits manually
            creds = flow.run_local_server(port=8080, open_browser=True)

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print("\n✅ Авторизация успешна! token.pickle сохранён.")
    else:
        print("✅ Токен уже действителен.")

if __name__ == '__main__':
    main()
