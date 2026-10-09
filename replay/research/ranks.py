"""Who was the day's #1, #2, #3 at each minute (10-06..10-08), for the speed
strategy's filter (the owner, 10-09 ~12:50pm: "the crowd and the volume ...
first, second and third of the day ... the gainers ... no more than a third").

  crowd rank  - money traded in the last 5 closed minutes, among the day's names
  gainer rank - the last close over the previous day's close, among the names
                up 10%+ (the scanner's bar)

The names: the bot's recorded 1-minute bars (replay/data/<day>/<SYM>.csv - the
scanner's names; 10-06 and 10-07 only, from claude/zealous-ramanujan-br3gay)
plus the Webull minute bars of the traded names (secdump/bars/<day>.json; all
10-08 has). The previous close: the daily file for 10-06 (10-05's close),
then the last regular-hours close of the day before from the minute bars.
10-08 ranks only among the 17 names the bots traded - a weaker universe."""
import csv, glob, json, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _epoch(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_minutes(rec_dir, webull_dir, day):
    """{sym: {minute epoch: (close, volume, session)}}."""
    out = {}
    for f in glob.glob(os.path.join(rec_dir, day, "*.csv")):
        sym = os.path.basename(f)[:-4]
        d = out.setdefault(sym, {})
        for r in csv.DictReader(open(f)):
            t = int(_epoch(r["time"]))
            d[t] = (float(r["close"]), float(r["volume"]), r["session"])
    wf = os.path.join(webull_dir, day + ".json")
    if os.path.exists(wf):
        for sym, rows in json.load(open(wf)).items():
            d = out.setdefault(sym, {})
            for r in rows:
                t = int(_epoch(r[0]))
                d.setdefault(t, (float(r[4]), float(r[5]), r[6]))
    return out


def last_rth_close(minutes):
    rth = [(t, c) for t, (c, v, s) in minutes.items() if s == "RTH"]
    return max(rth)[1] if rth else None


class Ranks:
    def __init__(self, rec_dir, webull_dir, daily_file, days):
        daily = json.load(open(daily_file))
        self.by_day = {}
        prev = {}
        for sym, rows in daily.items():                       # 10-05's close
            for r in rows:
                if r[0] == "2026-10-05":
                    prev[sym] = r[4]
        for day in days:
            mins = load_minutes(rec_dir, webull_dir, day)
            self.by_day[day] = self._rank(mins, prev)
            prev = {s: c for s, m in mins.items() if (c := last_rth_close(m))} or prev

    @staticmethod
    def _rank(mins, prev):
        """{minute epoch: {sym: (crowd rank, gainer rank or 99, gain)}}."""
        allm = sorted({t for m in mins.values() for t in m})
        if not allm:
            return {}
        first, last = allm[0], allm[-1]
        out = {}
        lastc = {}
        for t in range(first, last + 60, 60):
            money, gain = {}, {}
            for sym, m in mins.items():
                if t in m:
                    lastc[sym] = m[t][0]
                dol = sum(m[k][0] * m[k][1] for k in range(t - 240, t + 60, 60) if k in m)
                if dol > 0:
                    money[sym] = dol
                if sym in lastc and prev.get(sym):
                    g = lastc[sym] / prev[sym] - 1
                    if g >= 0.10:
                        gain[sym] = g
            cr = {s: i + 1 for i, s in enumerate(sorted(money, key=lambda s: -money[s]))}
            gr = {s: i + 1 for i, s in enumerate(sorted(gain, key=lambda s: -gain[s]))}
            out[t] = {s: (cr.get(s, 99), gr.get(s, 99), gain.get(s, 0.0)) for s in set(cr) | set(gr)}
        return out

    def at(self, day, sym, t):
        """The ranks of the last closed minute before t: (crowd, gainer, gain)."""
        d = self.by_day.get(day, {})
        m = int(t // 60) * 60 - 60
        return d.get(m, {}).get(sym, (99, 99, 0.0))
