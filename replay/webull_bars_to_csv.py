"""
Turn saved Webull bar results into replay data.

  Minute bars -> replay/data/<day>/<SYMBOL>.csv
      python3 replay/webull_bars_to_csv.py --day 2026-10-02 RESULT_FILE [...]

  Daily bars  -> replay/data/<day>/meta.json (Thursday's close as pre_close,
                 Friday's open/high/low/volume to check the minute bars by)
      python3 replay/webull_bars_to_csv.py --day 2026-10-02 --daily RESULT_FILE [...]

Inputs are the raw text get_stock_bars_single (a JSON list of bars, newest
first) or get_stock_bars (up to 20 symbols, {"result": [{"symbol", "result":
[bars]}]}) returned. Minute bars are written oldest first, every value copied
exactly as Webull sent it. For minute bars, each symbol's regular-session
open/high/low/close is then printed next to meta.json's daily figures, so a
short or mangled pull shows at a glance.
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
FIELDS = ("time", "trading_session", "open", "high", "low", "close", "volume")


def bars_by_symbol(path: Path):
    """{symbol: [bar dict, ...]} from either result shape."""
    raw = path.read_text()
    start = min(i for i in (raw.find("["), raw.find("{")) if i >= 0)
    data = json.loads(raw[start:])
    out = {}
    if isinstance(data, dict):                          # get_stock_bars
        for item in data.get("result", []):
            out.setdefault(item["symbol"], []).extend(item.get("result") or [])
    else:                                               # get_stock_bars_single
        for b in data:
            out.setdefault(b["symbol"], []).append(b)
    return out


def write_minutes(sym, bars, out_dir: Path):
    rows = sorted({tuple(b[k] for k in FIELDS) for b in bars})
    with open(out_dir / (sym + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("time", "session", "open", "high", "low", "close", "volume"))
        w.writerows(rows)
    return rows


def et_date(stamp: str):
    return datetime.fromisoformat(stamp.replace("+0000", "+00:00")).astimezone(ET).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--daily", action="store_true", help="inputs are D bars -> meta.json")
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    day = datetime.strptime(args.day, "%Y-%m-%d").date()
    out_dir = REPO / "replay" / "data" / args.day
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    if args.daily:
        for path in args.files:
            for sym, bars in bars_by_symbol(path).items():
                bars = sorted(bars, key=lambda b: b["time"])
                today = [b for b in bars if et_date(b["time"]) == day]
                before = [b for b in bars if et_date(b["time"]) < day]
                entry = meta.get(sym, {})
                if before:
                    entry["pre_close"] = float(before[-1]["close"])
                if today:
                    t = today[-1]
                    entry.update(open=float(t["open"]), high=float(t["high"]),
                                 low=float(t["low"]), volume=int(float(t["volume"])))
                meta[sym] = entry
        meta.setdefault("_source", "Webull daily bars; pre_close = the last close before %s"
                        % args.day)
        meta_path.write_text(json.dumps(meta, indent=1, sort_keys=True))
        print("meta.json: %d symbols, %d without a previous close"
              % (len([k for k in meta if not k.startswith("_")]),
                 len([k for k, v in meta.items()
                      if not k.startswith("_") and "pre_close" not in v])))
        return

    print("%-5s %5s  %-29s  %-29s  %s" % ("SYM", "bars", "RTH open/high/low/close",
                                         "daily open/high/low", "match"))
    for path in args.files:
        for sym, bars in sorted(bars_by_symbol(path).items()):
            rows = write_minutes(sym, bars, out_dir)
            rth = [r for r in rows if r[1] == "RTH"]
            got = (float(rth[0][2]), max(float(r[3]) for r in rth),
                   min(float(r[4]) for r in rth), float(rth[-1][5])) if rth else None
            m = meta.get(sym, {})
            want = tuple(m.get(k) for k in ("open", "high", "low"))
            ok = bool(got) and abs(got[1] - (m.get("high") or got[1])) < 0.011 and \
                abs(got[2] - (m.get("low") or got[2])) < 0.011
            print("%-5s %5d  %-29s  %-29s  %s" % (
                sym, len(rows),
                "/".join("%g" % x for x in got) if got else "no RTH bars",
                "/".join("%g" % x for x in want if x is not None) or "-",
                "high+low OK" if ok else "CHECK"))


if __name__ == "__main__":
    main()
