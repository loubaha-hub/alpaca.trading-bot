"""Sanity-check one bar file: python3 check_csv.py SYMBOL.csv"""
import csv, sys
from datetime import datetime
rows = list(csv.DictReader(open(sys.argv[1])))
bad, prev = [], None
for i, r in enumerate(rows):
    o, h, l, c, v = (float(r[k]) for k in ("open", "high", "low", "close", "volume"))
    t = datetime.fromisoformat(r["time"].replace("+0000", "+00:00"))
    if h < max(o, c) or l > min(o, c) or v < 0:
        bad.append((i, "ohlc", r))
    if prev and t <= prev:
        bad.append((i, "order", r))
    prev = t
print("rows", len(rows), "| first", rows[0]["time"], "| last", rows[-1]["time"])
print("volume_sum", int(sum(float(r["volume"]) for r in rows)),
      "| high", max(float(r["high"]) for r in rows),
      "| low", min(float(r["low"]) for r in rows))
print("problems", len(bad), bad[:3])
