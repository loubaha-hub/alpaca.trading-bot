#!/usr/bin/env python3
"""parse.py - the 2026-10-08 trade audit, rebuilt from the bot's own log lines.

Reads   raw/<SYM>.jsonl   ({"timestamp", "message"} per line - every Render log
                           line that contains the symbol, around each trade)
        book.json          (optional: the BOOK "CLOSED n trades ... realised"
                           totals to cross-check against)
Writes  trades.json        (one record per trade: decision, order, fill, stop,
                           market quotes, exit trigger, sells, exit, computed
                           fields, rule flags, and an ms timeline)
        summary.md         (per-strategy flag table, worst 10, BOOK check,
                           data gaps, parsing problems)

Re-runnable: drop more raw/<SYM>.jsonl files (or longer ones) in and run again.
Only the standard library is used. Usage:  python3 parse.py [--dir DIR]

Log formats are those of r34.py (VERSION v31-r34.28). Every number in the
output is copied from a log line or computed from logged numbers; anything the
log does not show is null.
"""
import argparse
import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone

ET = timezone(timedelta(hours=-4))          # 2026-10-08 is EDT (UTC-4)
STRATS = ("v36", "v36b", "v37")
LOOKBACK_MS = 30_000          # how far before a fill to look for its decision
QUOTE_PRE_MS = 30_000         # quotes kept from this long before the decision
JUST_AFTER_MS = 2_000         # "the bid at/just after the fill": within this
EPS = 1e-6

# r34.py constants the rules and the stop explanations refer to
FURIOUS_STOP_CENTS = 0.10     # V36_FURIOUS_STOP_CENTS
FURIOUS_STOP_MAX = 0.08       # V36_FURIOUS_STOP_MAX
LEVEL_GIVE = 0.01             # V36_LEVEL_GIVE
MIN_STOP_PCT = 0.01           # MIN_STOP_PCT
V36B_MAX_STOP = 0.03          # V36B.MAX_STOP
V37_FURIOUS_SPEED = 0.30      # V37_FURIOUS_SPEED
V37_STOP_MIN, V37_STOP_MAX = 0.03, 0.08
SWEEP_BIG = 10.0              # V37_SWEEP_BIG: 0.20 under it, 0.30 over

PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
                    r"(INFO|WARNING|ERROR|CRITICAL) (.*)$")
TAG = re.compile(r"^\[(v36b|v36|v37)\] (.*)$")
F = r"(-?\d+(?:\.\d+)?)"

PATTERNS = [
    ("furious", re.compile(r"^FURIOUS (\S+) at ([\d.]+): speed ([\d.]+), 5s ([+-]?[\d.]+)% "
                           r"on \$([\d.]+)k")),
    ("enter37", re.compile(r"^ENTER (\S+) (\d+) @ ([\d.]+) \(print ([\d.]+)\) = \$(\d+) "
                           r"\(([\d.]+)% of equity\) - (.*?), buy (\d+) today \| crowd "
                           r"#(\d+), \$(\d+)k in (\d+) min \| stop ([\d.]+) \| adds at "
                           r"([\d.]+) and ([\d.]+) \| speed ([\d.]+) \| score (\S+) \((.*)\)$")),
    ("enter", re.compile(r"^ENTER (\S+) (\d+) @ ([\d.]+) \(print ([\d.]+)\) = \$(\d+) "
                         r"\(([\d.]+)% of equity\) \| stop ([\d.]+) \(([\d.]+)% away\) \| "
                         r"(\S+) trigger ([\d.]+)")),
    ("full", re.compile(r"^(\S+) FULL POSITION (\d+) shares at once \(furious\), buy (\d+) "
                        r"today - stop ([\d.]+), line \$([\d.]+)")),
    ("starter_sized", re.compile(r"^(\S+) STARTER sized for its stop: (\d+) -> (\d+) shares "
                                 r"\(\$(\d+)\) - the stop ([\d.]+) is ([\d.]+)% under "
                                 r"([\d.]+), \$(\d+) at risk")),
    ("starter", re.compile(r"^(\S+) STARTER (\d+) shares \(a tenth of a full position\), "
                           r"buy (\d+) today - adds at ([\d.]+) and ([\d.]+)")),
    ("buyshort", re.compile(r"^(\S+) BUY SHORT - wanted (\d+), got (\d+) at a limit up to "
                            r"(\S+): (.*)$")),
    ("add36", re.compile(r"^(\S+) ADD to (\d+)% of a full position: \+(\d+) @ ([\d.]+) -> "
                         r"(\d+) shares, entry ([\d.]+), floor ([\d.]+)")),
    ("add37", re.compile(r"^ADD (\S+) to (\d+)% of a position: \+(\d+) @ ([\d.]+) -> (\d+) "
                         r"shares, average ([\d.]+), stop ([\d.]+)")),
    ("stopraise", re.compile(r"^(\S+) held past \$([\d.]+): the stop up to ([\d.]+) "
                             r"\(entry ([\d.]+)\)")),
    ("atstop", re.compile(r"^(\S+) the market ([\d.]+) x ([\d.]+) is at the stop ([\d.]+) - out")),
    ("selling", re.compile(r"^\s+(\S+) tape .* \(selling: (.+)\)$")),
    ("buying", re.compile(r"^\s+(\S+) tape .* \(buying\)$")),
    ("sell_limit", re.compile(r"^(\S+) SELL (\d+) at a limit ([\d.]+) \(bid ([\d.]+)\)")),
    ("sell_market", re.compile(r"^(\S+) SELL (\d+) at MARKET")),
    ("cancel", re.compile(r"^cancelled (\d+) working order\(s\) on (\S+)")),
    ("exit", re.compile(r"^(EXIT|TRIM) (\S+) (\S+) (\d+) @ ([\d.]+) \| trigger print ([\d.]+) "
                        r"x (\d+) cond (\[.*?\]|-), (?:([\d.]+)s old|age unknown) \| entry "
                        r"([\d.]+) peak ([\d.]+) stop ([\d.]+) \| held (\d+)s \| P/L "
                        r"([+-][\d.]+) \(([+-][\d.]+)% of the trade, ([+-][\d.]+)% of the "
                        r"account\)")),
    ("ignored", re.compile(r"^IGNORED (\S+) print ([\d.]+) - the market is ([\d.]+) x ([\d.]+)")),
    ("tape_held", re.compile(r"^TAPE (\S+) held ([+-][\d.]+)% \| (.*)$")),
    ("whynot", re.compile(r"^WHY-NOT (\S+) px ([\d.]+) \| (.*?) \| (.*)$")),
    ("skip", re.compile(r"^SKIP (\S+) at ([\d.]+) - (.*)$")),
    ("notconfirmed", re.compile(r"^(\S+) TRIGGER NOT CONFIRMED - print ([\d.]+).*? reached "
                                r"([\d.]+) but the ask is ([\d.]+)")),
    ("trim_note", re.compile(r"^(\S+) TRIM to (\d+)% of the account - room for (\S+)")),
    ("holds_none", re.compile(r"^(\S+): (?:the )?broker holds none")),
    ("still_holding", re.compile(r"^(\S+) STILL HOLDING")),
]
BOOK_ROW = re.compile(r"^\s+([A-Z][A-Z0-9.]*)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
                      r"([+-][\d.]+)\s+([+-][\d.]+)%\s+(\d+)m$")
ASK_IN_REASON = re.compile(r"the ask ([\d.]+) (?:is back at|fell back to) the high ([\d.]+)")
FILLED_UP_TO = re.compile(r"filled at up to ([\d.]+) \(the ask \+ ([\d.]+)\)")


def ms_of(iso):
    """'2026-10-08T12:06:44.547Z' -> epoch ms."""
    d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return int(round(d.timestamp() * 1000))


def iso_of(ms):
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (ms % 1000)


def et_of(ms):
    d = datetime.fromtimestamp(ms / 1000, tz=ET)
    return d.strftime("%H:%M:%S.") + "%03d" % (ms % 1000)


def r4(x):
    return None if x is None else round(x, 4)


def cents(x):
    return None if x is None else round(100 * x, 2)


def half_under(price):
    """V36.half_under: the whole or half dollar at or under the price."""
    return int(price * 2 + 1e-9) / 2.0 if price > 0 else 0.0


def parse_line(rec, seq, sym_file, problems):
    msg = rec["message"]
    ms = ms_of(rec["timestamp"])
    ev = {"ms": ms, "seq": seq, "file": sym_file, "raw": msg, "strat": None,
          "kind": "other", "sym": None, "level": None}
    m = PREFIX.match(msg)
    if not m:
        b = BOOK_ROW.match(msg)
        if b:
            ev.update(kind="book_row", sym=b.group(1), shares=int(b.group(2)),
                      entry=float(b.group(3)), last=float(b.group(4)),
                      stop=float(b.group(5)), pl=float(b.group(6)),
                      pct=float(b.group(7)), held_min=int(b.group(8)))
        else:
            problems.append({"file": sym_file, "time": iso_of(ms),
                             "problem": "line without a timestamp prefix, not a BOOK row",
                             "line": msg})
        return ev
    ev["level"] = m.group(2)
    body = m.group(3)
    t = TAG.match(body)
    if not t:
        ev["kind"] = "untagged"          # ROSTER, day highs, health, ...
        return ev
    ev["strat"], rest = t.group(1), t.group(2)
    for kind, rx in PATTERNS:
        g = rx.match(rest)
        if not g:
            continue
        ev["kind"] = kind
        G = g.groups()
        if kind == "furious":
            ev.update(sym=G[0], price=float(G[1]), speed=float(G[2]),
                      move5s_pct=float(G[3]), dollars_k=float(G[4]))
        elif kind == "enter37":
            acc = re.match(r"ACCELERATING ([\d.]+), (\d+)% of the account", G[6])
            ev.update(sym=G[0], shares=int(G[1]), fill=float(G[2]), print=float(G[3]),
                      dollars=int(G[4]), pct_equity=float(G[5]), sizing=G[6],
                      accel=float(acc.group(1)) if acc else None,
                      buy_n=int(G[7]), crowd_rank=int(G[8]), crowd_k=int(G[9]),
                      stop=float(G[11]), add1=float(G[12]), add2=float(G[13]),
                      speed=float(G[14]), score=G[15], score_parts=G[16])
            ev["kind"] = "enter"
        elif kind == "enter":
            ev.update(sym=G[0], shares=int(G[1]), fill=float(G[2]), print=float(G[3]),
                      dollars=int(G[4]), pct_equity=float(G[5]), stop=float(G[6]),
                      stop_away_pct=float(G[7]), trigger_kind=G[8], trigger=float(G[9]))
        elif kind == "full":
            ev.update(sym=G[0], shares=int(G[1]), buy_n=int(G[2]), stop=float(G[3]),
                      line=float(G[4]))
        elif kind == "starter_sized":
            ev.update(sym=G[0], from_shares=int(G[1]), shares=int(G[2]), stop=float(G[4]),
                      stop_pct=float(G[5]), price=float(G[6]), risk=int(G[7]))
        elif kind == "starter":
            ev.update(sym=G[0], shares=int(G[1]), buy_n=int(G[2]), add1=float(G[3]),
                      add2=float(G[4]))
        elif kind == "buyshort":
            ev.update(sym=G[0], wanted=int(G[1]), got=int(G[2]), cap=G[3], reason=G[4])
            f = FILLED_UP_TO.search(G[4])
            if f:
                ev.update(limit=float(f.group(1)), over_ask=float(f.group(2)))
            a = ASK_IN_REASON.search(G[4])
            if a:
                ev.update(ask=float(a.group(1)), high=float(a.group(2)))
        elif kind == "add36":
            ev.update(sym=G[0], to_pct=int(G[1]), added=int(G[2]), price=float(G[3]),
                      shares=int(G[4]), entry=float(G[5]), stop=float(G[6]))
        elif kind == "add37":
            ev.update(sym=G[0], to_pct=int(G[1]), added=int(G[2]), price=float(G[3]),
                      shares=int(G[4]), entry=float(G[5]), stop=float(G[6]))
            ev["kind"] = "add36"
        elif kind == "stopraise":
            ev.update(sym=G[0], level=float(G[1]), stop=float(G[2]), entry=float(G[3]))
        elif kind == "atstop":
            ev.update(sym=G[0], bid=float(G[1]), ask=float(G[2]), stop=float(G[3]))
        elif kind == "selling":
            ev.update(sym=G[0], why=G[1])
        elif kind == "buying":
            ev.update(sym=G[0])
        elif kind == "sell_limit":
            ev.update(sym=G[0], qty=int(G[1]), limit=float(G[2]), bid=float(G[3]),
                      order="limit")
            ev["kind"] = "sell"
        elif kind == "sell_market":
            ev.update(sym=G[0], qty=int(G[1]), limit=None, bid=None, order="market")
            ev["kind"] = "sell"
        elif kind == "cancel":
            ev.update(sym=G[1], n=int(G[0]))
        elif kind == "exit":
            ev.update(action=G[0], why=G[1], sym=G[2], sold=int(G[3]), px=float(G[4]),
                      trig_px=float(G[5]), trig_size=int(G[6]), trig_cond=G[7],
                      trig_age_s=float(G[8]) if G[8] is not None else None,
                      entry=float(G[9]), peak=float(G[10]), stop=float(G[11]),
                      held_s=int(G[12]), pl=float(G[13]), pl_pct_trade=float(G[14]),
                      pl_pct_account=float(G[15]))
        elif kind == "ignored":
            ev.update(sym=G[0], print=float(G[1]), bid=float(G[2]), ask=float(G[3]))
        elif kind == "tape_held":
            ev.update(sym=G[0], held_pct=float(G[1]), tape=G[2])
        elif kind == "whynot":
            ev.update(sym=G[0], px=float(G[1]), crowd=G[2], why=G[3])
        elif kind == "skip":
            ev.update(sym=G[0], px=float(G[1]), why=G[2])
        elif kind == "notconfirmed":
            ev.update(sym=G[0], print=float(G[1]), trigger=float(G[2]), ask=float(G[3]))
        elif kind == "trim_note":
            ev.update(sym=G[0], to_pct=int(G[1]), room_for=G[2])
        elif kind in ("holds_none", "still_holding"):
            ev.update(sym=G[0])
        break
    else:
        problems.append({"file": sym_file, "time": iso_of(ms),
                         "problem": "strategy line in no known format", "line": msg})
    return ev


def load_events(raw_dir, problems):
    events = []
    seq = 0
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        sym_file = os.path.basename(path)[:-len(".jsonl")]
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError as e:
                    problems.append({"file": sym_file, "line_no": n,
                                     "problem": "bad JSON: %s" % e})
                    continue
                ev = parse_line(rec, seq, sym_file, problems)
                seq += 1
                if ev["sym"] is None and ev["kind"] not in ("untagged", "other"):
                    ev["sym"] = sym_file
                events.append(ev)
    # The same line can sit in two files only if it names two symbols (a
    # ROSTER line); trade lines name one. Keep the first copy of each line.
    seen, out = set(), []
    for ev in sorted(events, key=lambda e: (e["ms"], e["seq"])):
        k = (ev["ms"], ev["raw"])
        if k in seen and ev["kind"] != "book_row":
            continue
        seen.add(k)
        out.append(ev)
    return out


def describe(ev):
    """A short human line for the timeline."""
    k = ev["kind"]
    if k == "furious":
        return "FURIOUS at %.4f, speed %.2f, 5s %+.1f%% on $%.0fk" % (
            ev["price"], ev["speed"], ev["move5s_pct"], ev["dollars_k"])
    if k == "enter":
        return "ENTER %d @ %.4f (print %.4f), stop %.4f" % (
            ev["shares"], ev["fill"], ev["print"], ev["stop"])
    if k == "full":
        return "FULL POSITION %d, stop %.4f, line $%.2f, buy %d today" % (
            ev["shares"], ev["stop"], ev["line"], ev["buy_n"])
    if k == "starter":
        return "STARTER %d, buy %d today, adds at %.4f / %.4f" % (
            ev["shares"], ev["buy_n"], ev["add1"], ev["add2"])
    if k == "starter_sized":
        return "STARTER sized for its stop %.4f: %d -> %d shares at %.4f" % (
            ev["stop"], ev["from_shares"], ev["shares"], ev["price"])
    if k == "buyshort":
        return "BUY SHORT wanted %d got %d (cap %s): %s" % (
            ev["wanted"], ev["got"], ev["cap"], ev["reason"])
    if k == "add36":
        return "ADD +%d @ %.4f -> %d sh, entry %.4f, stop/floor %.4f" % (
            ev["added"], ev["price"], ev["shares"], ev["entry"], ev["stop"])
    if k == "stopraise":
        return "stop up to %.4f (held past $%.2f)" % (ev["stop"], ev["level"])
    if k == "atstop":
        return "the market %.4f x %.4f is at the stop %.4f - out" % (
            ev["bid"], ev["ask"], ev["stop"])
    if k == "selling":
        return "(selling: %s)" % ev["why"]
    if k == "buying":
        return "(buying) tape"
    if k == "sell":
        if ev["order"] == "market":
            return "SELL %d at MARKET" % ev["qty"]
        return "SELL %d limit %.2f (bid %.4f)" % (ev["qty"], ev["limit"], ev["bid"])
    if k == "cancel":
        return "cancelled %d working order(s)" % ev["n"]
    if k == "exit":
        return "%s %s %d @ %.4f, P/L %+.2f" % (ev["action"], ev["why"], ev["sold"],
                                              ev["px"], ev["pl"])
    if k == "ignored":
        return "IGNORED print %.4f - the market %.4f x %.4f" % (
            ev["print"], ev["bid"], ev["ask"])
    if k == "tape_held":
        return "TAPE held %+.1f%%" % ev["held_pct"]
    if k == "whynot":
        return "WHY-NOT px %.4f: %s" % (ev["px"], ev["why"])
    if k == "skip":
        return "SKIP at %.4f: %s" % (ev["px"], ev["why"])
    if k == "notconfirmed":
        return "TRIGGER NOT CONFIRMED: print %.4f, ask %.4f under trigger %.4f" % (
            ev["print"], ev["ask"], ev["trigger"])
    if k == "book_row":
        return "BOOK row: %d sh entry %.4f last %.4f stop %.4f" % (
            ev["shares"], ev["entry"], ev["last"], ev["stop"])
    return ev["raw"]


def quotes_of(ev):
    """Every bid / ask a line carries, with where it came from."""
    k = ev["kind"]
    if k == "ignored":
        return [dict(bid=ev["bid"], ask=ev["ask"], source="IGNORED line",
                     print=ev["print"])]
    if k == "atstop":
        return [dict(bid=ev["bid"], ask=ev["ask"], source="the market ... is at the stop")]
    if k == "sell" and ev.get("bid") is not None:
        return [dict(bid=ev["bid"], ask=None, source="SELL line (bid)")]
    if k == "notconfirmed":
        return [dict(bid=None, ask=ev["ask"], source="TRIGGER NOT CONFIRMED (ask)")]
    if k == "buyshort" and ev.get("ask") is not None:
        return [dict(bid=None, ask=ev["ask"], source="BUY SHORT reason (ask)")]
    return []


def prints_of(ev):
    k = ev["kind"]
    if k == "furious":
        return [dict(price=ev["price"], source="FURIOUS")]
    if k == "ignored":
        return [dict(price=ev["print"], source="IGNORED (off the market)")]
    if k == "enter":
        return [dict(price=ev["print"], source="ENTER decision print")]
    if k == "exit":
        return [dict(price=ev["trig_px"], size=ev["trig_size"], source="EXIT trigger print",
                     age_s=ev["trig_age_s"])]
    if k == "whynot":
        return [dict(price=ev["px"], source="WHY-NOT px")]
    if k == "skip":
        return [dict(price=ev["px"], source="SKIP")]
    if k == "notconfirmed":
        return [dict(price=ev["print"], source="TRIGGER NOT CONFIRMED print")]
    if k == "book_row":
        return [dict(price=ev["last"], source="BOOK row last")]
    return []


def explain_stop(strat, fill, stop, dprint, trigger, enter_stop, accel):
    """Which r34.py stop formula reproduces the logged stop (to 4 decimals)."""
    cands = [
        ("fill - 0.10 (V36_FURIOUS_STOP_CENTS)", fill - FURIOUS_STOP_CENTS),
        ("the whole/half dollar under the print - 0.01 (line stop)",
         half_under(dprint) - LEVEL_GIVE if dprint else None),
        ("1% under the fill (MIN_STOP_PCT floor: min(stop_ref, fill x 0.99))",
         fill * (1 - MIN_STOP_PCT)),
        ("3% under max(trigger, decision print) (v36b MAX_STOP)",
         max(trigger or 0, dprint or 0) * (1 - V36B_MAX_STOP) if (trigger or dprint) else None),
        ("8% under the decision print (V36_FURIOUS_STOP_MAX)",
         dprint * (1 - FURIOUS_STOP_MAX) if dprint else None),
        ("the ENTER-line stop (sizing stop_ref, unchanged)", enter_stop),
    ]
    hits = [name for name, v in cands if v is not None and abs(round(v, 4) - stop) < 6e-5]
    implied = 1 - stop / fill if fill else None
    if strat == "v37" and implied is not None and V37_STOP_MIN - 1e-4 <= implied <= V37_STOP_MAX + 1e-4:
        hits.append("v37 speed stop: fill x (1 - %.2f%%) (V37_STOP_SHARE of the last "
                    "minute's move, 3-8%%)" % (100 * implied))
    enter_only = "the ENTER-line stop (sizing stop_ref, unchanged)"
    if len(hits) > 1 and enter_only in hits:      # it only says the stop never moved
        hits.remove(enter_only)
    return hits, implied


def furious_ok(stop, fill):
    """F3's two allowed stops for a furious buy."""
    if abs(stop - (fill - FURIOUS_STOP_CENTS)) < 6e-5:
        return True
    lvl = stop + LEVEL_GIVE
    return abs(lvl * 2 - round(lvl * 2)) < 1e-6        # a whole or half dollar - 0.01


def build_trades(events, problems):
    by_key = {}
    for ev in events:
        if ev["strat"] and ev["sym"]:
            by_key.setdefault((ev["strat"], ev["sym"]), []).append(ev)
    by_sym = {}
    for ev in events:
        if ev["sym"]:
            by_sym.setdefault(ev["sym"], []).append(ev)

    trades = []
    for key, evs in sorted(by_key.items()):
        cur = None
        for ev in evs:
            if ev["kind"] == "enter":
                if cur is not None:
                    problems.append({"time": iso_of(ev["ms"]), "problem":
                                     "%s %s ENTER while a trade was open (no EXIT seen); "
                                     "the open one is closed without an EXIT" % key})
                    trades.append(cur)
                cur = {"key": key, "enter": ev, "after": []}
                continue
            if cur is None:
                continue
            cur["after"].append(ev)
            if ev["kind"] == "exit" and ev["action"] == "EXIT":
                trades.append(cur)
                cur = None
        if cur is not None:
            trades.append(cur)                      # still open at the end of the data
    trades.sort(key=lambda t: t["enter"]["ms"])

    # the previous EXIT of the same strategy on the same symbol
    last_exit = {}
    for tr in trades:
        ex = next((e for e in tr["after"] if e["kind"] == "exit" and e["action"] == "EXIT"),
                  None)
        tr["exit_ev"] = ex
    out = []
    for tr in trades:
        out.append(assemble(tr, by_key[tr["key"]], by_sym[tr["key"][1]], last_exit,
                            problems))
        if tr["exit_ev"]:
            last_exit[tr["key"]] = tr["exit_ev"]
    return out


def assemble(tr, key_evs, sym_evs, last_exit, problems):
    strat, sym = tr["key"]
    en = tr["enter"]
    ex = tr["exit_ev"]
    fill_ms, fill = en["ms"], en["fill"]
    prev = last_exit.get(tr["key"])
    lo = max(en["ms"] - LOOKBACK_MS, prev["ms"] + 1 if prev else 0)
    pre = [e for e in key_evs if lo <= e["ms"] <= en["ms"] and e["seq"] != en["seq"]
           and e["ms"] <= en["ms"]]
    pre = [e for e in pre if e["seq"] < en["seq"] or e["ms"] < en["ms"]]
    after = tr["after"]

    # ---- route -------------------------------------------------------------
    full = next((e for e in after[:6] if e["kind"] == "full"), None)
    starter = next((e for e in after[:6] if e["kind"] == "starter"), None)
    adds = [e for e in after if e["kind"] == "add36" and (not ex or e["ms"] <= ex["ms"])]
    buy_n = (full or starter or en).get("buy_n")
    if strat == "v37":
        accel = en.get("accel")
        base = ("accel (ACCELERATING %.2f%s)" % (accel, ", furious speed" if accel >=
                                                  V37_FURIOUS_SPEED else "")
                if accel is not None else "normal starter (a tenth of a position)")
        furious = bool(accel is not None and accel >= V37_FURIOUS_SPEED)
    else:
        accel = None
        if full:
            base, furious = "furious (FULL POSITION at once)", True
        elif starter:
            base, furious = "normal starter (a tenth of a full position)", False
        else:
            base, furious = "unknown (no FULL POSITION / STARTER line)", False
            problems.append({"time": iso_of(en["ms"]), "problem":
                             "%s %s ENTER without FULL POSITION/STARTER line" % (strat, sym)})
    route = base
    if buy_n and buy_n > 1:
        route += ", re-entry (buy %d today)" % buy_n
    if adds:
        route += ", + %d add(s)" % len(adds)

    # ---- decision ------------------------------------------------------------
    furs = [e for e in pre if e["kind"] == "furious"]
    sized = [e for e in pre if e["kind"] == "starter_sized"]
    decision = first = None
    dsource = None
    if furs:
        match = [e for e in furs if abs(e["price"] - en["print"]) < EPS]
        decision = match[-1] if match else furs[-1]
        first = furs[0]
        dsource = ("FURIOUS line at the ENTER print" if match else
                   "last FURIOUS line before the ENTER (none at the ENTER print)")
    elif sized:
        decision = first = sized[-1]
        dsource = "STARTER sized-for-its-stop line"
    attempts = [e for e in pre if e["kind"] == "buyshort"]
    filling = next((e for e in reversed(attempts)
                    if e["got"] > 0 and en["ms"] - e["ms"] <= 1500), None)
    failed = [e for e in attempts if e is not filling]
    buy_cancels = [e for e in pre if e["kind"] == "cancel"]
    if decision is not None:
        dprint, dspeed = decision["price"], decision.get("speed")
        d5 = decision.get("move5s_pct")
        dtime = decision["ms"]
    else:
        dprint, dspeed, d5, dtime = en["print"], en.get("speed"), None, None
    if strat == "v37":
        dspeed = en.get("speed")
    # sibling v36/v36b FURIOUS line nearest before a v37 fill: context only
    proxy = None
    if strat == "v37":
        sib = [e for e in sym_evs if e["kind"] == "furious" and e["strat"] != "v37"
               and 0 <= en["ms"] - e["ms"] <= 2000]
        if sib:
            s = sib[-1]
            proxy = {"time_utc": iso_of(s["ms"]), "from": s["strat"], "price": s["price"],
                     "move5s_pct": s["move5s_pct"], "speed": s["speed"],
                     "note": "another strategy's FURIOUS line - NOT v37's own decision"}

    # ---- order -------------------------------------------------------------
    if filling:
        wanted, got = filling["wanted"], filling["got"]
        lim = filling.get("limit")
        rule = ("the ask + %.2f" % filling["over_ask"]) if filling.get("over_ask") else None
        lim_src = "BUY SHORT line"
        implied_ask = r4(lim - filling["over_ask"]) if lim is not None and rule else None
        cap = filling["cap"]
    else:
        wanted = got = en["shares"]
        lim, implied_ask, cap = None, None, None
        sweep = 0.30 if (dprint or 0) >= SWEEP_BIG else 0.20
        if furious and strat != "v37":
            rule = "the ask + %.2f (code: furious sweep, not logged)" % sweep
        elif strat == "v37" and en.get("accel") is not None:
            rule = "the ask + %.2f (code: v37 fast sweep, not logged)" % sweep
        else:
            rule = "ask x 1.002, capped (code: FAST_BUY, not logged)"
        lim_src = "none - filled in full, so no BUY SHORT line"
    order = {
        "wanted": wanted, "got": got, "limit": lim, "limit_rule": rule,
        "limit_source": lim_src, "implied_ask_at_last_order": implied_ask,
        "cap": cap, "failed_attempts_before_fill": [
            {"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]), "wanted": e["wanted"],
             "got": e["got"], "reason": e["reason"]} for e in failed],
        "buy_side_cancels": [{"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"])}
                             for e in buy_cancels],
        "fill_time_utc": iso_of(fill_ms), "fill_time_et": et_of(fill_ms),
        "fill_price": fill, "dollars": en["dollars"], "pct_equity": en["pct_equity"],
        "decision_to_fill_ms": (fill_ms - dtime) if dtime is not None else None,
        "first_decision_to_fill_ms": (fill_ms - first["ms"]) if first else None,
    }

    # ---- stop --------------------------------------------------------------
    stop_first = en["stop"]
    stop_final = full["stop"] if full else en["stop"]
    stop_changes = []
    for e in after:
        if ex and e["ms"] > ex["ms"]:
            break
        if e["kind"] == "stopraise":
            stop_changes.append({"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                                 "stop": e["stop"], "why": "held past $%.2f" % e["level"]})
        elif e["kind"] == "add36":
            stop_changes.append({"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                                 "stop": e["stop"], "why": "ADD: floor/stop at the new "
                                 "average %.4f" % e["entry"]})
    stop = {"first_in_enter": stop_first, "final_at_entry": stop_final,
            "final_source": "FULL POSITION line" if full else "ENTER line",
            "line": full["line"] if full else None, "changes": stop_changes,
            "at_exit": ex["stop"] if ex else None}

    # ---- exit trigger, sells, exit -------------------------------------------
    end_ms = ex["ms"] if ex else (after[-1]["ms"] if after else fill_ms)
    win = [e for e in after if e["ms"] <= end_ms]
    selling = [e for e in win if e["kind"] == "selling"]
    trig = selling[0] if selling else None
    trigger = None
    if trig:
        at = next((e for e in win if e["kind"] == "atstop"
                   and 0 <= trig["ms"] - e["ms"] <= 50), None)
        trigger = {"time_utc": iso_of(trig["ms"]), "time_et": et_of(trig["ms"]),
                   "reason": trig["why"], "fill_to_trigger_ms": trig["ms"] - fill_ms,
                   "source": ("the market mid at/under the stop (BID_STOP): %.4f x %.4f "
                              "vs stop %.4f" % (at["bid"], at["ask"], at["stop"])) if at
                   else "a print (the EXIT line's trigger print)",
                   "bid": at["bid"] if at else None, "ask": at["ask"] if at else None}
    t0 = trig["ms"] if trig else None
    sells = [e for e in win if e["kind"] == "sell" and (t0 is None or e["ms"] >= t0)]
    cancels = [e for e in win if e["kind"] == "cancel" and t0 is not None and e["ms"] >= t0]
    exit_rec = None
    if ex:
        exit_rec = {"time_utc": iso_of(ex["ms"]), "time_et": et_of(ex["ms"]),
                    "action": ex["action"], "why": ex["why"], "shares": ex["sold"],
                    "price": ex["px"], "trigger_print": ex["trig_px"],
                    "trigger_print_size": ex["trig_size"], "trigger_cond": ex["trig_cond"],
                    "trigger_print_age_s": ex["trig_age_s"],
                    "trigger_print_time_approx_utc": iso_of(int(t0 - 1000 * ex["trig_age_s"]))
                    if (t0 is not None and ex["trig_age_s"] is not None) else None,
                    "entry_avg": ex["entry"], "peak": ex["peak"], "stop": ex["stop"],
                    "held_s": ex["held_s"], "pl": ex["pl"],
                    "pl_pct_trade": ex["pl_pct_trade"], "pl_pct_account": ex["pl_pct_account"]}
        calc = (ex["px"] - ex["entry"]) * ex["sold"]
        # px and entry are printed to 4 decimals; P/L uses the unrounded values
        if abs(calc - ex["pl"]) > 0.0001 * ex["sold"] + 0.011:
            problems.append({"time": iso_of(ex["ms"]), "problem": "%s %s EXIT P/L %.2f != "
                             "(px - entry) x shares = %.2f" % (strat, sym, ex["pl"], calc)})
    if abs(en["dollars"] - en["shares"] * fill) > 1.0:
        problems.append({"time": iso_of(en["ms"]), "problem": "%s %s ENTER $%d != shares x "
                         "fill %.2f" % (strat, sym, en["dollars"], en["shares"] * fill)})
    trims = [e for e in win if e["kind"] == "exit" and e["action"] == "TRIM"]
    held = en["shares"] + sum(e["added"] for e in after if e["kind"] == "add36"
                              and (t0 is None or e["ms"] < t0))
    if sells and sells[0]["qty"] != held:
        problems.append({"time": iso_of(sells[0]["ms"]), "problem": "%s %s first SELL %d != "
                         "shares held %d" % (strat, sym, sells[0]["qty"], held)})
    if any(b["qty"] > a["qty"] for a, b in zip(sells, sells[1:])):
        problems.append({"time": iso_of(sells[0]["ms"]), "problem": "%s %s SELL quantities "
                         "rise between orders" % (strat, sym)})
    if ex and ex["action"] == "EXIT" and ex["sold"] != held:
        problems.append({"time": iso_of(ex["ms"]), "problem": "%s %s EXIT sold %d != shares "
                         "held %d" % (strat, sym, ex["sold"], held)})
    notes = []
    for a in adds:
        nxt = next((e for e in win if e["kind"] == "selling" and e["ms"] >= a["ms"]), None)
        if nxt and nxt["ms"] - a["ms"] <= 1000:
            notes.append("ADD at %s set the stop to the new average %.4f; the stop sold %d ms "
                         "later (%s)" % (et_of(a["ms"]), a["stop"], nxt["ms"] - a["ms"],
                                         nxt["why"]))
    if failed:
        notes.append("%d buy attempt(s) got nothing before the one that filled" % len(failed))

    # ---- market: quotes and prints, every strategy's lines ---------------------
    q_from = (first["ms"] if first else (dtime if dtime else fill_ms)) - QUOTE_PRE_MS
    quotes, prints = [], []
    for e in sym_evs:
        if e["ms"] < q_from or e["ms"] > end_ms:
            continue
        for q in quotes_of(e):
            q.update(time_utc=iso_of(e["ms"]), time_et=et_of(e["ms"]),
                     ms_from_fill=e["ms"] - fill_ms, by=e["strat"])
            quotes.append(q)
        for p in prints_of(e):
            p.update(time_utc=iso_of(e["ms"]), time_et=et_of(e["ms"]),
                     ms_from_fill=e["ms"] - fill_ms, by=e["strat"])
            prints.append(p)

    # ---- timeline: this strategy's own lines, decision-30s .. exit -------------
    timeline = []
    tl_from = max(q_from, prev["ms"] + 1) if prev else q_from   # not the last trade's tail
    own = [e for e in key_evs if tl_from <= e["ms"] <= end_ms]
    for e in own:
        timeline.append({"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                         "ms_from_fill": e["ms"] - fill_ms, "kind": e["kind"],
                         "what": describe(e)})
    for e in sym_evs:
        if e["kind"] == "book_row" and q_from <= e["ms"] <= end_ms and \
                e["entry"] == en["fill"] and e["shares"] in (en["shares"],) + tuple(
                    a["shares"] for a in adds):
            timeline.append({"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                             "ms_from_fill": e["ms"] - fill_ms, "kind": "book_row",
                             "what": describe(e)})
    timeline.sort(key=lambda r: r["time_utc"])

    # ---- computed fields -----------------------------------------------------
    bid_after = next((q for q in quotes if q["ms_from_fill"] >= 0 and q["bid"] is not None),
                     None)
    peak = ex["peak"] if ex else None
    comp = {
        "first_bid_at_or_after_fill": bid_after["bid"] if bid_after else None,
        "first_bid_source": bid_after["source"] if bid_after else None,
        "first_bid_ms_after_fill": bid_after["ms_from_fill"] if bid_after else None,
        "fill_minus_bid_cents": cents(fill - bid_after["bid"]) if bid_after else None,
        "stop_minus_bid_at_fill_cents": cents(stop_final - bid_after["bid"]) if bid_after
        else None,
        "exit_vs_stop_cents": cents(ex["px"] - ex["stop"]) if ex and ex["why"] == "stop"
        else None,
        "peak_gain_cents": cents(peak - fill) if peak is not None else None,
        "peak_minus_avg_entry_cents": cents(peak - ex["entry"]) if ex else None,
        "peak_equals_decision_print": bool(peak is not None and abs(peak - en["print"]) < EPS
                                           and en["print"] > fill + EPS),
        "rebuy_gap_s": round(((first["ms"] if first else (dtime or fill_ms)) - prev["ms"])
                             / 1000, 3) if prev else None,
        "rebuy_gap_to_fill_s": round((fill_ms - prev["ms"]) / 1000, 3) if prev else None,
        "five_sec_move_pct": d5,
        "fill_to_trigger_ms": trigger["fill_to_trigger_ms"] if trigger else None,
        "trigger_to_first_sell_ms": (sells[0]["ms"] - t0) if (sells and t0) else None,
        "trigger_to_exit_ms": (ex["ms"] - t0) if (ex and t0 is not None) else None,
        "n_sell_orders": len(sells),
        "n_sell_cancels": len(cancels),
        "fill_to_exit_ms": (ex["ms"] - fill_ms) if ex else None,
    }

    rec = {
        "id": "%s-%s-%s" % (strat, sym, et_of(fill_ms)[:8].replace(":", "")),
        "strategy": strat, "account": {"v36": "T6HH", "v36b": "AUES", "v37": "P28T"}[strat],
        "symbol": sym, "route": route, "furious": furious, "buy_n_today": buy_n,
        "decision": {
            "time_utc": iso_of(dtime) if dtime is not None else None,
            "time_et": et_of(dtime) if dtime is not None else None,
            "source": dsource if decision else ("not logged (v37 logs no line before the "
                                                "buy)" if strat == "v37" else "not logged"),
            "first_decision_time_utc": iso_of(first["ms"]) if first else None,
            "first_decision_time_et": et_of(first["ms"]) if first else None,
            "first_decision_five_sec_move_pct": first.get("move5s_pct") if first else None,
            "first_decision_print": first.get("price") if first else None,
            "n_furious_lines_before_fill": len(furs),
            "print": dprint, "speed": dspeed, "five_sec_move_pct": d5,
            "five_sec_dollars_k": decision.get("dollars_k") if decision else None,
            "enter_print": en["print"], "trigger": en.get("trigger"),
            "trigger_kind": en.get("trigger_kind"),
            "v37_accel": en.get("accel"), "v37_score": en.get("score"),
            "v37_score_parts": en.get("score_parts"), "v37_crowd_rank": en.get("crowd_rank"),
            "five_sec_move_proxy_from_sibling": proxy,
        },
        "order": order, "stop": stop, "trigger": trigger,
        "sells": [{"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                   "ms_from_trigger": e["ms"] - t0 if t0 else None, "qty": e["qty"],
                   "order": e["order"], "limit": e["limit"], "bid": e["bid"]} for e in sells],
        "sell_cancels": [{"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]),
                          "ms_from_trigger": e["ms"] - t0} for e in cancels],
        "adds": [{"time_utc": iso_of(e["ms"]), "time_et": et_of(e["ms"]), "added": e["added"],
                  "price": e["price"], "shares_after": e["shares"], "avg_entry": e["entry"],
                  "stop": e["stop"]} for e in adds],
        "trims": [{"time_utc": iso_of(e["ms"]), "why": e["why"], "shares": e["sold"],
                   "price": e["px"], "pl": e["pl"]} for e in trims],
        "exit": exit_rec, "pl": (ex["pl"] if ex else 0.0) + sum(e["pl"] for e in trims),
        "computed": comp, "notes": notes, "market_quotes": quotes, "market_prints": prints,
        "timeline": timeline,
    }
    rec["flags"] = flags_for(rec, en, ex, furious, stop_final, dprint, accel)
    return rec


def flags_for(rec, en, ex, furious, stop_final, dprint, accel):
    c, strat, fill = rec["computed"], rec["strategy"], en["fill"]
    out = []
    # F1 - a furious (v36/v36b) or fast (v37 accel) buy whose own 5-second move <= 0
    if (furious or en.get("accel") is not None) and c["five_sec_move_pct"] is not None \
            and c["five_sec_move_pct"] <= 0:
        out.append({"flag": "F1", "name": "furious_or_fast_buy_with_5s_down",
                    "evidence": "decision %s at %.4f: 5s %+.1f%% (speed %.2f)" % (
                        rec["decision"]["time_et"], dprint, c["five_sec_move_pct"],
                        rec["decision"]["speed"] or 0)})
    fd = rec["decision"]["first_decision_five_sec_move_pct"]
    if fd is not None and fd <= 0 and not out and c["five_sec_move_pct"] is not None:
        rec["decision"]["note"] = ("the first FURIOUS attempt (%s, 5s %+.1f%%) missed; the "
                                   "buy that filled was decided at 5s %+.1f%%" % (
                                       rec["decision"]["first_decision_time_et"], fd,
                                       c["five_sec_move_pct"]))
        rec["notes"].append(rec["decision"]["note"] + " (F1 judged on the filling decision)")
    # F2 - the bid at / just after the fill already under the stop
    b = c["first_bid_at_or_after_fill"]
    if b is not None and b < stop_final - EPS and c["first_bid_ms_after_fill"] <= JUST_AFTER_MS:
        out.append({"flag": "F2", "name": "bid_gap_over_stop",
                    "evidence": "fill %.4f, stop %.4f, bid %.4f %d ms after the fill (%s); "
                                "the stop triggered %s ms after the fill" % (
                                    fill, stop_final, b, c["first_bid_ms_after_fill"],
                                    c["first_bid_source"], c["fill_to_trigger_ms"])})
    # F3 - a furious buy's stop neither fill - 0.10 nor the whole/half dollar - 0.01
    if furious and not furious_ok(stop_final, fill):
        hits, implied = explain_stop(strat, fill, stop_final, dprint, en.get("trigger"),
                                     en["stop"], accel)
        out.append({"flag": "F3", "name": "stop_not_from_fill",
                    "evidence": "stop %.4f vs fill - 0.10 = %.4f (%.2f%% under the fill); "
                                "matches: %s" % (stop_final, fill - 0.10, 100 * implied,
                                                 "; ".join(hits) or "no known formula"),
                    "explanation": stop_story(strat, fill, stop_final, dprint,
                                              en.get("trigger"), en["stop"], hits)})
    # F4 - a slow sale
    if (c["trigger_to_exit_ms"] is not None and c["trigger_to_exit_ms"] > 2000) or \
            c["n_sell_orders"] > 2:
        out.append({"flag": "F4", "name": "slow_sale",
                    "evidence": "trigger -> EXIT %s ms, %d sell orders, %d cancels" % (
                        c["trigger_to_exit_ms"], c["n_sell_orders"], c["n_sell_cancels"])})
    # F5 - a stop exit filled more than 5c under the stop
    if ex and ex["why"] == "stop" and ex["px"] < ex["stop"] - 0.05 - EPS:
        out.append({"flag": "F5", "name": "stop_fill_slippage",
                    "evidence": "stop %.4f, filled %.4f (%.1fc under)" % (
                        ex["stop"], ex["px"], 100 * (ex["stop"] - ex["px"]))})
    # F6 - bought back within 10 s of the same strategy's previous exit
    if c["rebuy_gap_s"] is not None and c["rebuy_gap_s"] <= 10:
        out.append({"flag": "F6", "name": "quick_rebuy",
                    "evidence": "decision %.3f s (fill %.3f s) after the previous EXIT" % (
                        c["rebuy_gap_s"], c["rebuy_gap_to_fill_s"])})
    # F7 - a v37 giveback exit on a 0-2c gain
    if strat == "v37" and ex and ex["why"] == "giveback" and ex["peak"] - ex["entry"] <= 0.02 + EPS:
        out.append({"flag": "F7", "name": "v37_tiny_giveback",
                    "evidence": "peak %.4f - entry %.4f = %.1fc" % (
                        ex["peak"], ex["entry"], 100 * (ex["peak"] - ex["entry"]))})
    # F8 - up 10c+ and sold at or under the fill
    if ex and c["peak_gain_cents"] is not None and c["peak_gain_cents"] >= 10 - EPS and \
            ex["px"] <= fill + EPS:
        out.append({"flag": "F8", "name": "gain_given_back",
                    "evidence": "fill %.4f, peak %.4f (+%.1fc), exit %.4f" % (
                        fill, ex["peak"], c["peak_gain_cents"], ex["px"])})
    # F9 - never a cent above the fill
    if ex and abs(ex["peak"] - fill) < EPS:
        out.append({"flag": "F9", "name": "never_above_fill",
                    "evidence": "peak %.4f == fill %.4f" % (ex["peak"], fill)})
    return out


def stop_story(strat, fill, stop, dprint, trigger, enter_stop, hits):
    f10 = fill - FURIOUS_STOP_CENTS
    if strat == "v37":
        if any(h.startswith("v37 speed stop") for h in hits):
            return ("v37 stop_for(): max(fill x (1 - stop_pct), fill - 0.10) = max(%.4f, "
                    "%.4f): the speed-based stop is the tighter one, so it was kept; the "
                    "whole/half-dollar line (%.2f - 0.01) is lower still." % (
                        stop, f10, half_under(dprint)))
        if any(h.startswith("1% under") for h in hits):
            return ("v37: the line stop min(line - 0.01 = %.4f, fill x 0.99 = %.4f) raised the "
                    "stop to the 1%% floor %.4f, above fill - 0.10 = %.4f." % (
                        half_under(dprint) - LEVEL_GIVE, fill * 0.99, stop, f10))
        return "v37: stop %.4f; no single r34.py formula reproduces it exactly." % stop
    ref = max(trigger or 0, dprint or 0)
    if any(h.startswith("1% under") for h in hits):
        return ("%s: the stop was set from the decision print, not the fill: stop_ref = "
                "max(bar low, %s8%% under %.4f = %.4f, line %.2f) sat above the fill-based "
                "floor, so min(stop_ref, fill x 0.99) took %.4f (1%% under the fill %.4f); "
                "fill - 0.10 = %.4f is lower, so max() kept %.4f." % (
                    strat, ("3%% under %.4f = %.4f, " % (ref, ref * 0.97)) if strat == "v36b"
                    else "", dprint, dprint * 0.92, half_under(dprint) - LEVEL_GIVE, stop,
                    fill, f10, stop))
    if any(h.startswith("3% under") for h in hits):
        return ("v36b MAX_STOP: stop_ref = 3%% under max(trigger %.4f, print %.4f) = %.4f, "
                "under the 1%% floor %.4f so min() kept it, and above fill - 0.10 = %.4f so "
                "max() kept it." % (trigger or 0, dprint, stop, fill * 0.99, f10))
    if any(h.startswith("8% under") for h in hits):
        return ("V36_FURIOUS_STOP_MAX: 8%% under the print %.4f = %.4f, above fill - 0.10 = "
                "%.4f." % (dprint, stop, f10))
    if any(h.startswith("the ENTER-line stop") for h in hits):
        return ("%s: stop %.4f = the sizing stop_ref from the ENTER line (the last 1-minute "
                "bar's low for a furious 'hod' entry - the bar itself is not logged), above "
                "fill - 0.10 = %.4f, so max() kept it; 8%% under the print = %.4f and the "
                "line %.2f are lower." % (strat, stop, f10, dprint * 0.92,
                                          half_under(dprint) - LEVEL_GIVE))
    if hits:
        return "%s: stop %.4f = %s." % (strat, stop, hits[0])
    return ("%s: stop %.4f (ENTER line said %.4f); no single r34.py formula reproduces it "
            "exactly - likely the bar-low stop_ref from the setup, not logged." % (
                strat, stop, enter_stop))


# ---- summary -------------------------------------------------------------------

FLAG_NAMES = [("F1", "furious_or_fast_buy_with_5s_down"), ("F2", "bid_gap_over_stop"),
              ("F3", "stop_not_from_fill"), ("F4", "slow_sale"),
              ("F5", "stop_fill_slippage"), ("F6", "quick_rebuy"),
              ("F7", "v37_tiny_giveback"), ("F8", "gain_given_back"),
              ("F9", "never_above_fill")]


def money(x):
    return ("+" if x >= 0 else "-") + "$" + format(abs(x), ",.2f")


def write_summary(path, trades, book, problems, raw_dir):
    L = []
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    first = min(t["order"]["fill_time_et"] for t in trades) if trades else "-"
    last = max((t["exit"]["time_et"] for t in trades if t["exit"]), default="-")
    L.append("# Trade audit - 2026-10-08 (r34.py v31-r34.28)\n")
    L.append("Built %s by parse.py from %d raw/<SYM>.jsonl files (Render log lines that "
             "name the symbol, 90 s before each decision to 30 s after each exit). Times are "
             "ET (UTC-4) to the millisecond, from the bot's own log stamps. %d trades, first "
             "fill %s ET, last exit %s ET.\n" % (
                 gen, len(glob.glob(os.path.join(raw_dir, "*.jsonl"))), len(trades), first,
                 last))
    # per strategy
    L.append("## Per strategy\n")
    L.append("| strategy (account) | trades | up / down | P/L (sum of EXIT lines) |")
    L.append("|---|---:|---:|---:|")
    for s in STRATS:
        ts = [t for t in trades if t["strategy"] == s]
        up = sum(1 for t in ts if t["pl"] > 0)
        L.append("| %s (%s) | %d | %d / %d | %s |" % (
            s, {"v36": "T6HH", "v36b": "AUES", "v37": "P28T"}[s], len(ts), up, len(ts) - up,
            money(sum(t["pl"] for t in ts))))
    L.append("")
    # BOOK
    L.append("## BOOK cross-check\n")
    if book:
        L.append("| BOOK line (ET) | strategy | BOOK trades | BOOK realised | trades here "
                 "(exits up to then) | sum here | difference |")
        L.append("|---|---|---:|---:|---:|---:|---:|")
        for b in book:
            bms = ms_of(b["time_utc"])
            ts = [t for t in trades if t["strategy"] == b["strategy"] and t["exit"]
                  and ms_of(t["exit"]["time_utc"]) <= bms]
            sm = round(sum(t["pl"] for t in ts), 2)
            L.append("| %s | %s | %d | %s | %d | %s | %s |" % (
                et_of(bms)[:8], b["strategy"], b["trades"], money(b["realised"]), len(ts),
                money(sm), "match" if (len(ts) == b["trades"] and abs(sm - b["realised"])
                                       < 0.005) else money(round(sm - b["realised"], 2))))
        L.append("")
    else:
        L.append("No book.json - not checked.\n")
    # flags
    L.append("## Flags (count / summed P/L of the flagged trades)\n")
    L.append("| flag | " + " | ".join(STRATS) + " | all |")
    L.append("|---|" + "---:|" * (len(STRATS) + 1))
    for code, name in FLAG_NAMES:
        cells = []
        for s in list(STRATS) + [None]:
            ts = [t for t in trades if (s is None or t["strategy"] == s)
                  and any(f["flag"] == code for f in t["flags"])]
            cells.append("%d / %s" % (len(ts), money(sum(t["pl"] for t in ts))))
        L.append("| %s %s | %s |" % (code, name, " | ".join(cells)))
    ts = [t for t in trades if t["flags"]]
    L.append("| any flag | %s |" % " | ".join(
        "%d / %s" % (len([t for t in ts if s is None or t["strategy"] == s]),
                     money(sum(t["pl"] for t in ts if s is None or t["strategy"] == s)))
        for s in list(STRATS) + [None]))
    L.append("\nF1 is judged only on the trade's own FURIOUS line: v37 logs no 5-second move "
             "(see data gaps). A trade can carry several flags, so rows overlap.\n")
    # worst 10
    L.append("## The 10 worst trades\n")
    L.append("| # | trade | route | decision -> fill | fill | stop | exit | P/L | flags |")
    L.append("|---:|---|---|---:|---:|---:|---|---:|---|")
    for i, t in enumerate(sorted(trades, key=lambda t: t["pl"])[:10], 1):
        o, x = t["order"], t["exit"] or {}
        L.append("| %d | %s %s %s | %s | %s | %.4f | %.4f | %s %.4f @ %s | %s | %s |" % (
            i, t["strategy"], t["symbol"], o["fill_time_et"], t["route"],
            ("%d ms" % o["decision_to_fill_ms"]) if o["decision_to_fill_ms"] is not None
            else "n/a", o["fill_price"], t["stop"]["final_at_entry"], x.get("why"),
            x.get("price", 0), x.get("time_et"), money(t["pl"]),
            ", ".join(f["flag"] for f in t["flags"]) or "-"))
    L.append("")
    for t in sorted(trades, key=lambda t: t["pl"])[:10]:
        if t["flags"]:
            L.append("- **%s**: " % t["id"] + "; ".join(
                "%s %s" % (f["flag"], f["evidence"]) for f in t["flags"]))
    L.append("")
    # evidence per flag
    L.append("## Flag evidence\n")
    for code, name in FLAG_NAMES:
        ts = [t for t in trades if any(f["flag"] == code for f in t["flags"])]
        L.append("### %s %s - %d trade(s), %s\n" % (code, name, len(ts),
                                                    money(sum(t["pl"] for t in ts))))
        for t in ts:
            f = next(f for f in t["flags"] if f["flag"] == code)
            L.append("- %s (%s): %s%s" % (t["id"], money(t["pl"]), f["evidence"],
                                         (" - " + f["explanation"]) if f.get("explanation")
                                         else ""))
        L.append("")
    nt = [t for t in trades if t.get("notes")]
    if nt:
        L.append("## Other things the log shows (not one of F1-F9)\n")
        for t in nt:
            L.append("- %s (%s): %s" % (t["id"], money(t["pl"]), "; ".join(t["notes"])))
        L.append("")
    # all trades
    L.append("## Every trade\n")
    L.append("| trade | route | 5s at decision | decision -> fill ms | fill | bid after fill "
             "| stop | fill -> trigger ms | trigger -> EXIT ms | sells | exit | peak | P/L | "
             "flags |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|")
    for t in trades:
        c, o, x = t["computed"], t["order"], t["exit"] or {}
        L.append("| %s | %s | %s | %s | %.4f | %s | %.4f | %s | %s | %d | %s %.4f | %s | %s "
                 "| %s |" % (
                     t["id"], t["route"],
                     ("%+.1f%%" % c["five_sec_move_pct"]) if c["five_sec_move_pct"] is not None
                     else "-",
                     o["decision_to_fill_ms"] if o["decision_to_fill_ms"] is not None else "-",
                     o["fill_price"],
                     ("%.4f (+%d ms)" % (c["first_bid_at_or_after_fill"],
                                         c["first_bid_ms_after_fill"]))
                     if c["first_bid_at_or_after_fill"] is not None else "-",
                     t["stop"]["final_at_entry"],
                     c["fill_to_trigger_ms"] if c["fill_to_trigger_ms"] is not None else "-",
                     c["trigger_to_exit_ms"] if c["trigger_to_exit_ms"] is not None else "-",
                     c["n_sell_orders"], x.get("why"), x.get("price", 0),
                     ("%.4f" % x["peak"]) if x else "-", money(t["pl"]),
                     ", ".join(f["flag"] for f in t["flags"]) or "-"))
    L.append("")
    # data gaps
    n37 = [t for t in trades if t["strategy"] == "v37"]
    nodec = [t for t in trades if t["decision"]["time_utc"] is None]
    nobid = [t for t in trades if t["computed"]["first_bid_ms_after_fill"] is None
             or t["computed"]["first_bid_ms_after_fill"] > JUST_AFTER_MS]
    mkt = [t for t in trades if any(s["order"] == "market" for s in t["sells"])]
    proxy_down = [t for t in n37 if t["decision"]["five_sec_move_proxy_from_sibling"]
                  and t["decision"]["five_sec_move_proxy_from_sibling"]["move5s_pct"] <= 0]
    L.append("## Data gaps - what the logs do not show\n")
    L.append("- **The quote at the decision moment.** No line logs the bid x ask when a buy "
             "is decided. Quotes exist only where a line happens to print them: IGNORED "
             "prints (at most one per strategy per symbol per 30 s), \"the market B x A is at "
             "the stop\", SELL limit lines (bid only, premarket), TRIGGER NOT CONFIRMED and "
             "BUY SHORT reasons (ask only). %d of %d trades have no logged bid within %d ms "
             "after the fill." % (len(nobid), len(trades), JUST_AFTER_MS))
    L.append("- **Every print.** The log has no tape: only the prints a decision or an "
             "IGNORED line names (FURIOUS, ENTER print, EXIT trigger print, WHY-NOT px, "
             "SKIP, IGNORED). The peak in the EXIT line is the bot's own s.peak, not a print "
             "list; for v36/v36b starters it starts at max(decision print, fill), so a peak "
             "equal to the decision print may never have traded after the fill.")
    L.append("- **v37's decision time, speed-at-decision and 5-second move.** v37 logs no "
             "line before it buys (no FURIOUS), so its decision -> fill latency is unknown "
             "and F1 cannot be judged for it (%d v37 trades; %d had a v36/v36b FURIOUS line "
             "with a 5s move <= 0 within 2 s before the v37 fill - context only, recorded as "
             "five_sec_move_proxy_from_sibling)." % (len(n37), len(proxy_down)))
    L.append("- **Decision time for v36/v36b normal starters** is logged only when the "
             "\"STARTER sized for its stop\" line fires; %d of %d trades have no decision "
             "timestamp at all." % (len(nodec), len(trades)))
    L.append("- **Buy orders.** Order sends, order ids, each order's limit and partial fills "
             "are not logged. A limit appears only in a BUY SHORT line (the last order's "
             "\"filled at up to X (the ask + 0.20)\"); a buy that filled in full prints no "
             "BUY SHORT, so its limit is null and only the rule from the code is recorded. "
             "The fill time is the ENTER line's time (after the broker confirmed the average "
             "price), not the exchange fill time.")
    L.append("- **Sell orders.** Each SELL line is one order sent; its fill size and price "
             "are not logged - only the next SELL's smaller quantity and the EXIT's average "
             "price. Cancels say only \"cancelled 1 working order(s)\". %d trade(s) sold at "
             "MARKET (9:30-4:00): those lines carry no bid." % len(mkt))
    L.append("- **Stops in between.** Stop moves are logged only by \"held past $X\" and ADD "
             "lines; the trail stop, the 10-second leash and v37's giveback line are not "
             "logged until they fire (the EXIT line's stop field is s.stop, not the trail).")
    L.append("- **Exit trigger print time.** The EXIT line gives the trigger print's age at "
             "the sale's start; its time is approximated as (selling line - age).")
    L.append("- **Only the trade windows were fetched.** raw/<SYM>.jsonl holds the lines "
             "from 90-100 s before each trade's first logged decision (or its fill when no "
             "decision is logged) to 30 s after its EXIT, merged per symbol; lines between "
             "windows are not in the files. Render returns each log line with its own "
             "ingestion time; parse.py uses the bot's asctime (ms) instead.")
    L.append("- **BOOK row ownership.** BOOK table rows carry no strategy tag (the header "
             "line does, but it does not name the symbol); rows are attached to a trade only "
             "when shares and entry match.\n")
    # problems
    L.append("## Parsing problems\n")
    if problems:
        for p in problems:
            L.append("- %s" % json.dumps(p))
    else:
        L.append("- none: every strategy line matched a known r34.py format, every trade has "
                 "ENTER and EXIT, and every EXIT's P/L equals (price - entry) x shares to the "
                 "cent.")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    raw_dir = os.path.join(a.dir, "raw")
    problems = []
    events = load_events(raw_dir, problems)
    trades = build_trades(events, problems)
    book = None
    bp = os.path.join(a.dir, "book.json")
    if os.path.exists(bp):
        with open(bp, encoding="utf-8") as f:
            book = json.load(f)
    per = {}
    for s in STRATS:
        ts = [t for t in trades if t["strategy"] == s]
        per[s] = {"trades": len(ts), "pl": round(sum(t["pl"] for t in ts), 2),
                  "flags": {code: {"count": sum(1 for t in ts if any(
                      f["flag"] == code for f in t["flags"])),
                      "pl": round(sum(t["pl"] for t in ts if any(
                          f["flag"] == code for f in t["flags"])), 2)}
                      for code, _ in FLAG_NAMES}}
    doc = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "Render logs srv-daqp02flot8c73ffv6eg, r34.py v31-r34.28",
           "date": "2026-10-08", "timezone_note": "time_utc from the bot's log stamp; "
           "time_et = UTC-4", "n_events": len(events), "per_strategy": per,
           "book": book, "parse_problems": problems, "trades": trades}
    with open(os.path.join(a.dir, "trades.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    write_summary(os.path.join(a.dir, "summary.md"), trades, book, problems, raw_dir)
    for s in STRATS:
        print("%-5s %3d trades  P/L %+9.2f" % (s, per[s]["trades"], per[s]["pl"]))
    print("%d events, %d trades, %d parse problems" % (len(events), len(trades),
                                                       len(problems)))


if __name__ == "__main__":
    main()
