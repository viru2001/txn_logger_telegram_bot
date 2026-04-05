import json

DATETIME, TXN_TYPE, AMOUNT, CATEGORY, TITLE, NOTE, ACCOUNT = range(7)

def load_config():
    with open("configs/config.json", "r") as f:
        return json.load(f)

CONFIG = load_config()
