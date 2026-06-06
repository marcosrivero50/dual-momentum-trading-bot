"""
trade_journal.py — Logs every trade to a CSV you can open in Excel or Google Sheets.
"""

import csv
import os
from datetime import datetime

FILE = "trade_journal.csv"
COLUMNS = ["date", "time", "action", "symbol", "asset_class", "qty", "price", "notes"]


class TradeJournal:
    def __init__(self):
        self._buffer = []
        if not os.path.exists(FILE):
            with open(FILE, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=COLUMNS).writeheader()

    def log(self, action, symbol, qty, price, asset_class="stock", notes=""):
        now = datetime.now()
        self._buffer.append({
            "date":        now.strftime("%Y-%m-%d"),
            "time":        now.strftime("%H:%M:%S"),
            "action":      action,
            "symbol":      symbol,
            "asset_class": asset_class,
            "qty":         round(qty, 6),
            "price":       round(price, 4),
            "notes":       notes,
        })

    def save(self):
        if not self._buffer:
            return
        with open(FILE, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writerows(self._buffer)
        self._buffer = []
