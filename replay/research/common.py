"""Shared loading for the research scripts: replay/data minute bars by day."""
import csv, json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "replay" / "data"
OUT = REPO / "replay" / "out"
DAYS = sorted(p.name for p in DATA.iterdir() if p.is_dir() and p.name[:2] == "20")


@lru_cache(maxsize=None)
def load(day):
    """{symbol: (pre_close, [(time ET, open, high, low, close, volume), ...])}"""
    meta = json.loads((DATA/day/"meta.json").read_text())
    syms = {}
    for f in (DATA/day).glob("*.csv"):
        rows = []
        for r in csv.DictReader(open(f)):
            t = datetime.fromisoformat(r["time"].replace("+0000", "+00:00")).astimezone(ET)
            rows.append((t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])))
        rows.sort()
        m = meta.get(f.stem, {})
        if rows and m.get("pre_close"):
            syms[f.stem] = (m["pre_close"], rows)
    return syms


def hm(t):
    return t.hour*60 + t.minute
