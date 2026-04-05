# Cashew Tracker Telegram Bot

A Telegram bot to track expenses, log them into a Google Sheet, and generate Cashew app dark links for 1-click entry tracking.

## 🛠️ Setup Instructions

### 1. Get Telegram Bot Token
1. Go to Telegram and search for `@BotFather`.
2. Type `/newbot` and follow the instructions.
3. Copy the HTTP API **Token**.

### 2. Get Google Sheets Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Go to **APIs & Services > Library** and enable **Google Sheets API** and **Google Drive API**.
4. Go to **APIs & Services > Credentials**.
5. Click **Create Credentials > Service Account**.
6. Once created, go to the Service Account settings, navigate to the **Keys** tab, and select **Add Key > Create new key > JSON**.
7. Rename the downloaded JSON file to `credentials.json` and place it in the `configs/` folder.
8. **IMPORTANT:** Open your Google Sheet, click "Share" in the top right, and share it (Editor access) with the `client_email` found inside your `configs/credentials.json` file.

### 3. Setup Your Environment
1. Create a copy of `.env.example` and name it `.env`.
2. Open `.env` and paste your Telegram Token.
3. (Optional) Add your allowable user IDs to `.env` as `ALLOWED_TELEGRAM_IDS` (comma separated) to restrict access. Example: `ALLOWED_TELEGRAM_IDS=12345678,98765432`
4. Open your Google Sheet in your browser and copy its ID from the URL. (e.g. `https://docs.google.com/spreadsheets/d/<COPY_THIS_ID_HERE>/edit`). Set this as `GOOGLE_SHEET_ID` in `.env`.
5. Your Google Sheet should have the following headers (Row 1) in this exact order:
   `DateTime | Amount | Category | Title | Note | Account`

### 4. Running Locally
Make sure you have Python 3.9+ installed.
```bash
pip install -r requirements.txt
python main.py
```


