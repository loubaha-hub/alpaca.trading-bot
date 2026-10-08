"""Each account's fills (the "[vNN] history <day> #n:" log lines) as round trips:
a position opened from flat, its adds, closed when back to zero.

python3 roundtrips.py <lines file> [out.json]"""
import json, re, sys
from collections import defaultdict

HIST = re.compile(r"\[(\w+)\] history (\d{4}-\d\d-\d\d) #\d+: (.*)$")


def fills(path):
    out = defaultdict(list)                      # (bot, day) -> [(hms, side, sym, q, px)]
    seen = set()                                 # a whole line seen twice (a restart wrote it
    for line in open(path, encoding="utf-8"):    # again) counts once; two equal fills in one
        m = HIST.search(line.rstrip("\n"))       # second on one line are two orders
        if not m:
            continue
        bot, day, rows = m.groups()
        key = (bot, day, line[line.find("#"):].strip())
        if key in seen:
            continue
        seen.add(key)
        for r in rows.split("; "):
            t, side, sym, qp = r.split(" ")
            q, px = qp.split("@")
            out[(bot, day)].append((t, side, sym, float(q), float(px)))
    return out


def roundtrips(rows):
    """[{sym, open, close, buys: [(t, q, px)], sells: [...], pl, first_px, shares}]"""
    pos, cur, done = defaultdict(float), {}, []
    for t, side, sym, q, px in sorted(rows, key=lambda r: (r[0], r[1] != "B")):
        if side == "B":
            if pos[sym] <= 1e-9:
                cur[sym] = dict(sym=sym, open=t, buys=[], sells=[])
            cur[sym]["buys"].append((t, q, px))
            pos[sym] += q
        else:
            if sym not in cur:
                continue                          # a sale of a position from before the day
            cur[sym]["sells"].append((t, q, px))
            pos[sym] -= q
            if pos[sym] <= 1e-9:
                rt = cur.pop(sym)
                rt["close"] = t
                cost = sum(q * p for _, q, p in rt["buys"])
                got = sum(q * p for _, q, p in rt["sells"])
                rt["pl"] = round(got - cost, 2)
                rt["first_px"] = rt["buys"][0][2]
                rt["first_q"] = rt["buys"][0][1]
                rt["shares"] = sum(q for _, q, _ in rt["buys"])
                done.append(rt)
                pos[sym] = 0.0
    for sym, rt in cur.items():
        rt["close"] = None
        rt["pl"] = None
        done.append(rt)                            # still open at the end of the fills
    return done


if __name__ == "__main__":
    f = fills(sys.argv[1])
    res = {}
    for (bot, day), rows in sorted(f.items()):
        rts = roundtrips(rows)
        closed = [r for r in rts if r["pl"] is not None]
        res.setdefault(bot, {})[day] = rts
        print("%-5s %s: %3d fills, %3d round trips (%d open), %3d won, P/L %+9.2f" % (
            bot, day, len(rows), len(rts), len(rts) - len(closed), sum(r["pl"] > 0 for r in closed),
            sum(r["pl"] for r in closed)))
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], "w"), indent=0)
