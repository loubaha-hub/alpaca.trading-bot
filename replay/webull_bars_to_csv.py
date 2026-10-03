"""
Turn saved Webull get_stock_bars_single results into replay bar files.

    python3 replay/webull_bars_to_csv.py --day 2026-10-02 RESULT_FILE [RESULT_FILE ...]

Each input is the raw text a get_stock_bars_single call returned (a JSON list
of 1-minute bars, newest first). Each output is replay/data/<day>/<SYMBOL>.csv,
oldest first, every value copied exactly as Webull sent it. Then, per symbol,
the regular-session open/high/low/close is printed next to the daily figures
in replay/data/<day>/meta.json, so a short or mangled pull shows at a glance.
"""

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIELDS = ("time", "trading_session", "open", "high", "low", "close", "volume")


def convert(path: Path, out_dir: Path):
    raw = path.read_text()
    bars = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
    symbols = {b["symbol"] for b in bars}
    if len(symbols) != 1:
        raise SystemExit("%s: expected one symbol, got %s" % (path, sorted(symbols)))
    sym = symbols.pop()
    rows = sorted({tuple(b[k] for k in FIELDS) for b in bars})
    with open(out_dir / (sym + ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("time", "session", "open", "high", "low", "close", "volume"))
        w.writerows(rows)
    return sym, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    out_dir = REPO / "replay" / "data" / args.day
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    print("%-5s %5s  %-29s  %-29s  %s" % ("SYM", "bars", "RTH open/high/low/close",
                                         "daily open/high/low/close", "match"))
    for path in args.files:
        sym, rows = convert(path, out_dir)
        rth = [r for r in rows if r[1] == "RTH"]
        got = (float(rth[0][2]), max(float(r[3]) for r in rth),
               min(float(r[4]) for r in rth), float(rth[-1][5])) if rth else None
        m = meta.get(sym, {})
        want = tuple(m.get(k) for k in ("open", "high", "low")) + (None,)
        ok = got and abs(got[1] - (m.get("high") or got[1])) < 1e-6 and \
            abs(got[2] - (m.get("low") or got[2])) < 1e-6
        print("%-5s %5d  %-29s  %-29s  %s" % (
            sym, len(rows),
            "/".join("%g" % x for x in got) if got else "no RTH bars",
            "/".join("%g" % x for x in want if x is not None) or "-",
            "high+low OK" if ok else "CHECK"))


if __name__ == "__main__":
    main()
