"""Put SEC_DUMP's log lines (r34.34, 10-08 night) back together.

python3 secread.py <lines file, one Render log message a line, .gz ok> <out dir>

Writes, per window (a day, a symbol, the buys whose 30 minutes overlap):
    <out>/<day>_<sym>_<HHMMSS>.json.gz  {"day", "sym", "start" (epoch s), "end",
        "buys" ["HH:MM:SS.mmm" ET], "T": [[ms after start, price, size, conds]],
        "Q": [[ms, bid, ask, bid size, ask size]], "S": [[second after start, open,
        high, low, close, volume, prints, bid, ask, lowest bid]], "missing": [minute
        offsets with no data or a missing piece]}
and <out>/fills.json: {strategy: {day: [[ "HH:MM:SS", "B"/"S", sym, qty, price ]]}}
from the "[vNN] history <day> #n:" lines."""
import base64, glob, gzip, json, os, re, sys, zlib
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DATA = re.compile(r"SECDUMP (\d{4}-\d\d-\d\d) (\S+) (\d\d:\d\d:\d\d) (\d+) (\d+)/(\d+) (\S+)$")
WIN = re.compile(r"SECDUMP (\d{4}-\d\d-\d\d) (\S+) (\d\d:\d\d:\d\d)-(\d\d:\d\d:\d\d): (\d+) buys \(([^)]*)\)")
HIST = re.compile(r"\[(\w+)\] history (\d{4}-\d\d-\d\d) #\d+: (.*)$")


def epoch(day, hms):
    return datetime.fromisoformat(f"{day}T{hms}").replace(tzinfo=ET).timestamp()


def main(src, out):
    os.makedirs(out, exist_ok=True)
    pieces, wins, fills = {}, {}, {}
    opener = gzip.open if src.endswith(".gz") else open
    for line in opener(src, "rt", encoding="utf-8"):
        line = line.rstrip("\n")
        m = DATA.search(line)
        if m:
            day, sym, a, off, i, n, text = m.groups()
            pieces.setdefault((day, sym, a, int(off)), {})[int(i)] = (int(n), text)
            continue
        m = WIN.search(line)
        if m:
            day, sym, a, b, nb, buys = m.groups()
            wins[(day, sym, a)] = (b, buys.split())
            continue
        m = HIST.search(line)
        if m:
            name, day, rows = m.groups()
            dayrows = fills.setdefault(name, {}).setdefault(day, [])
            for r in rows.split("; "):
                t, side, sym, qp = r.split(" ")
                q, px = qp.split("@")
                row = [t, side, sym, float(q), float(px)]
                if row not in dayrows:        # a restart writes them again
                    dayrows.append(row)
    done = 0
    for (day, sym, a), (b, buys) in sorted(wins.items()):
        start, end = epoch(day, a), epoch(day, b)
        if end < start:
            end += 86400
        T, Q, S, missing = [], [], [], []
        for off in range(0, int(end - start + 59) // 60 * 60, 60):
            p = pieces.get((day, sym, a, off))
            if not p or len(p) != next(iter(p.values()))[0]:
                missing.append(off)
                continue
            try:
                blob = json.loads(zlib.decompress(base64.b64decode("".join(p[k][1] for k in sorted(p)))))
            except Exception:
                missing.append(off)               # a piece that does not decode: left out
                continue
            T += blob["T"]; Q += blob["Q"]; S += blob["S"]
        rec = dict(day=day, sym=sym, start=start, end=end, buys=buys, T=T, Q=Q, S=S, missing=missing)
        path = os.path.join(out, f"{day}_{sym}_{a.replace(':', '')}.json.gz")
        with gzip.open(path, "wt") as f:
            json.dump(rec, f, separators=(",", ":"))
        done += 1
        print(f"{day} {sym} {a}-{b} buys {len(buys)}: {len(T)} trades, {len(Q)} quotes, "
              f"{len(S)} seconds, missing minutes {missing[:6]}{'...' if len(missing) > 6 else ''}")
    for name in fills:
        for day in fills[name]:
            fills[name][day].sort()
    with open(os.path.join(out, "fills.json"), "w") as f:
        json.dump(fills, f, indent=0)
    print(f"{done} windows; fills: " + ", ".join(
        f"{k} " + "/".join(f"{d[5:]} {len(v)}" for d, v in sorted(days.items()))
        for k, days in sorted(fills.items())))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
