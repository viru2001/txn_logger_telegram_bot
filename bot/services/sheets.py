import os

import gspread
from google.oauth2.service_account import Credentials


def get_sheet():
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("credentials.json not found! Please add your Service Account JSON.")
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID not found in environment variables.")
    return client.open_by_key(sheet_id).sheet1
