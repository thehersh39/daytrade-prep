#!/usr/bin/env python3
"""Morning day-trade screen. Runs on GitHub Actions before the open and writes data.json
(same shape the Morning Day-Trade Prep page and email expect). Source: Yahoo Finance via yfinance."""
import json, math, re, sys, time, datetime as dt
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf

CT, ET = ZoneInfo("America/Chicago"), ZoneInfo("America/New_York")
T = ("NVDA AMD AVGO TSM ASML ARM QCOM INTC MRVL AMAT LRCX KLAC SMCI SMH SOXX MU WDC STX SNDK AAPL MSFT GOOGL AMZN META TSLA "
     "XOM CVX COP OXY SLB HAL XLE VST CEG DHI LEN PHM TOL KBH HD LOW ITB XHB PLTR COIN HOOD MSTR NFLX CRWD SPY QQQ IWM RSP "
     "XLK XLC XLY XLF XLI XLB XLP XLU XLV XLRE IGV PG KO PEP WMT COST JNJ LLY UNH ABBV MRK NEE DUK SO JPM GS PGR CB GLD GDX TLT").split()
ETF = set("SMH SOXX XLE ITB XHB SPY QQQ IWM RSP XLK XLC XLY XLF XLI XLB XLP XLU XLV XLRE IGV GLD GDX TLT".split())
log = lambda *a: print(*a, file=sys.stderr, flush=True)
now_ct = dt.datetime.now(CT)
today = now_ct.strftime("%Y%m%d")

# ---- daily candles ----
raw = yf.download(T, period="6mo", interval="1d", group_by="ticker", auto_adjust=False, threads=True, progress=False)
B = {}
for t in T:
    try:
        df = raw[t].dropna(subset=["Open", "High", "Low", "Close"])
        bars = [dict(d=i.strftime("%Y%m%d"), o=float(r.Open), h=float(r.High), l=float(r.Low), c=float(r.Close), v=float(r.Volume or 0))
                for i, r in df.iterrows()]
        if bars and bars[-1]["d"] == today: bars.pop()   # keep levels "prior session" if run after the open
        if len(bars) >= 60: B[t] = bars
    except Exception as e:
        log("history fail", t, e)
if "SPY" not in B: sys.exit("No SPY history; Yahoo did not answer")
bad = [t for t in T if t not in B]
asof = B["SPY"][-1]["d"]

# ---- week of sessions ----
wk, d = [], now_ct.date()
while len(wk) < 5:
    if d.weekday() < 5: wk.append([d.strftime("%m-%d"), f"{d.strftime('%a')} {d.month}/{d.day}"])
    d += dt.timedelta(days=1)
wkset = {w[0] for w in wk}

# ---- quote info (premarket, earnings, market cap) for list + market-wide movers ----
def trending():
    out = []
    try:
        from curl_cffi import requests as cr
        j = cr.get("https://query1.finance.yahoo.com/v1/finance/trending/US?count=30", impersonate="chrome", timeout=20).json()
        out += [q["symbol"] for q in j["finance"]["result"][0]["quotes"]]
    except Exception as e: log("trending fail", e)
    for sid in ("day_gainers", "day_losers"):
        try:
            r = yf.screen(sid, count=15)
            out += [q["symbol"] for q in r.get("quotes", []) if abs(q.get("regularMarketChangePercent") or 0) >= 5]
        except Exception as e: log("screen fail", sid, e)
    return [s for s in out if re.fullmatch(r"[A-Z]{1,5}", s or "")]
U = list(dict.fromkeys([t for t in T if t not in ETF] + trending()))[:130]

def info(t):
    for k in range(2):
        try: return t, yf.Ticker(t).info or {}
        except Exception: time.sleep(1.5)
    return t, {}
with ThreadPoolExecutor(8) as ex: Q = dict(ex.map(info, U + [t for t in T if t in ETF]))

def et_parts(ts):
    x = dt.datetime.fromtimestamp(ts, ET); return x.strftime("%Y%m%d"), x.hour
def earn_ts(q): return q.get("earningsTimestamp") or q.get("earningsTimestampStart")

PRE = {}
for t, q in Q.items():
    p = q.get("preMarketPrice")
    pt = q.get("preMarketTime") or 0
    if p and (q.get("marketState") in ("PRE", "PREPRE") or dt.datetime.fromtimestamp(pt, CT).date() == now_ct.date()):
        PRE[t] = round(float(p), 2)

# ---- setups (same rules as the original browser screen) ----
f = lambda v: round(v + 0.0, 2)
R = []
for t, D in B.items():
    n = len(D); i = n - 1
    C = [b["c"] for b in D]; H = [b["h"] for b in D]; L = [b["l"] for b in D]; V = [b["v"] for b in D]
    TR = [D[0]["h"] - D[0]["l"]] + [max(D[k]["h"] - D[k]["l"], abs(D[k]["h"] - C[k-1]), abs(D[k]["l"] - C[k-1])) for k in range(1, n)]
    avg = lambda X, a, b: sum(X[a:b+1]) / (b - a + 1)
    atr = avg(TR, i-13, i); c = C[i]; atrp = atr / c * 100
    vavg = avg(V, i-20, i-1); rvol = V[i] / vavg if vavg else 1
    dv = avg([V[k] * C[k] for k in range(n)], i-19, i) / 1e6
    s20, s50 = avg(C, i-19, i), avg(C, i-49, i); w0 = max(0, n-90)
    h90, l90, h5, l5 = max(H[w0:]), min(L[w0:]), max(H[i-4:]), min(L[i-4:])
    rng = H[i] - L[i]; clv = (c - L[i]) / rng if rng else .5; chg = (c / C[i-1] - 1) * 100
    inside = H[i] < H[i-1] and L[i] > L[i-1]; nr7 = rng <= min(D[k]["h"] - D[k]["l"] for k in range(i-6, i))
    tags, bias = [], 0
    if h90 - c <= atr and clv >= .6: tags.append("Near 90-day high"); bias += 1
    if c - l90 <= atr and clv <= .4: tags.append("Near 90-day low"); bias -= 1
    if inside: tags.append("Inside day")
    elif nr7: tags.append("NR7 coil")
    if abs(c - C[i-1]) >= 1.3 * atr and rvol >= 1.3:
        if chg > 0 and clv >= .75: tags.append("Momentum up"); bias += 1
        elif chg < 0 and clv <= .25: tags.append("Momentum down"); bias -= 1
    if abs(L[i] - s50) <= .35 * atr and c > s50 and clv >= .6 and s20 > s50: tags.append("Bounce off 50-day"); bias += 1
    if abs(H[i] - s50) <= .35 * atr and c < s50 and clv <= .4 and s20 < s50: tags.append("Rejected at 50-day"); bias -= 1
    if abs(L[i] - s20) <= .3 * atr and c > s20 and clv >= .6 and c > s50: tags.append("Bounce off 20-day"); bias += 1
    trend = 1 if c > s20 > s50 else -1 if c < s20 < s50 else 0
    if not bias and tags: bias = trend
    ewk = ""
    et = earn_ts(Q.get(t, {}))
    if et:
        md = dt.datetime.fromtimestamp(et, ET).strftime("%m-%d")
        if md in wkset: ewk = md
    sc = round(min(atrp, 6) * 7 + min(rvol, 3) * 10 + len(tags) * 12 + (8 if dv > 500 else 4 if dv > 150 else 0) + (6 if ewk else 0))
    R.append(dict(t=t, c=f(c), chg=round(chg, 1), atr=f(atr), atrp=round(atrp, 1), rvol=round(rvol, 1), dv=round(dv), h=f(H[i]), l=f(L[i]),
                  h5=f(h5), l5=f(l5), h90=f(h90), l90=f(l90), s20=f(s20), s50=f(s50), clv=round(clv, 2), tags=tags, bias=bias, trend=trend, ewk=ewk, sc=sc))
R.sort(key=lambda r: -r["sc"])
num = lambda v: (f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
flagged = [r for r in R if r["tags"]]
rows = ["|".join(num(r[k]) if k != "tags" else "/".join(r["tags"]) for k in
        ("t", "c", "chg", "atr", "atrp", "rvol", "dv", "h", "l", "h5", "l5", "h90", "l90", "s20", "s50", "clv", "tags", "bias", "trend", "ewk", "sc")) for r in flagged]
others = [",".join([r["t"], num(r["c"]), num(r["atrp"]), num(r["rvol"]), r["ewk"]]) for r in R if not r["tags"]]

def b36(x):
    s = "0123456789abcdefghijklmnopqrstuvwxyz"; return s[x // 36] + s[x % 36]
fits = sorted([r for r in flagged if 1 <= r["atr"] <= 10], key=lambda r: ((0 if r["atr"] <= 6 else 1), -r["sc"]))[:14]
enc2 = {}
for r in fits:
    S = B[r["t"]][-90:]; nums = [v for b in S for v in (b["o"], b["h"], b["l"], b["c"])]; lo, hi = min(nums), max(nums)
    enc2[r["t"]] = [S[0]["d"][2:], S[-1]["d"][2:], round(lo, 2), round(hi, 2),
                    "".join(b36(round((v - lo) / (hi - lo) * 1295)) for b in S for v in (b["o"], b["h"], b["l"], b["c"]))]

# ---- in play on news ----
cutoff = dt.datetime.strptime(asof, "%Y%m%d").replace(hour=16, tzinfo=ET).timestamp()
KW = re.compile(r"upgrade|downgrade|FDA|approv|acqui|merger|buyout|takeover|deal|guidance|outlook|forecast|recall|lawsuit|probe|investigat|offering|buyback|CEO|resign|contract|partner|beats|misses|tariff|halt|split|layoff|stake|settle|antitrust|delist|bankrupt", re.I)
pct = lambda v: ("+" if v >= 0 else "−") + f"{abs(v):.1f}%"
def news_for(t):
    q = Q.get(t, {})
    if q.get("quoteType") != "EQUITY" or (q.get("marketCap") or 0) < 2e9 or (q.get("regularMarketPrice") or q.get("currentPrice") or 0) < 5: return None
    why, kind = [], ""
    et = earn_ts(q)
    if et:
        dte, hr = et_parts(et)
        if dte == today and hr < 12: why.append("Earnings before the open today"); kind = "E"
        elif dte == asof and hr >= 16: why.append("Reported after the close"); kind = "E"
        elif dte == today and hr >= 16: why.append("Earnings after the close today"); kind = kind or "E"
    try:
        ud = yf.Ticker(t).upgrades_downgrades
        if ud is not None and len(ud):
            ud = ud.reset_index()
            for _, x in ud.iterrows():
                gd = x["GradeDate"]; ts = gd.timestamp() if hasattr(gd, "timestamp") else 0
                if ts < cutoff: continue
                a = str(x.get("Action", "")).lower()
                if a not in ("up", "down", "init"): continue
                why.append(f"Upgraded to {x['ToGrade']} at {x['Firm']}" if a == "up" else f"Downgraded to {x['ToGrade']} at {x['Firm']}" if a == "down" else f"{x['Firm']} starts at {x['ToGrade']}")
                kind = kind or "R"
                if sum(1 for w in why if " at " in w or "starts at" in w) >= 2: break
    except Exception as e: log("ud fail", t, e)
    prev = q.get("regularMarketPreviousClose") or q.get("previousClose")
    pm = (PRE[t] / q["regularMarketPrice"] - 1) * 100 if t in PRE and q.get("regularMarketPrice") else None
    rm = q.get("regularMarketChangePercent")
    in_list = t in T
    mover = (pm is not None and abs(pm) >= 3) or (not in_list and rm is not None and abs(rm) >= 5)
    head = ""
    try:
        items = yf.Search(t, news_count=6, max_results=1).news or []
        nm = re.sub(r"[^A-Za-z0-9&-]", "", ((q.get("shortName") or q.get("longName") or "").split() or [""])[0])
        names = re.compile(rf"\b{re.escape(t)}\b" + (rf"|\b{re.escape(nm)}" if len(nm) >= 3 and nm.upper() not in ("THE", "INC") else ""), re.I)
        items = [n for n in items if (n.get("providerPublishTime") or 0) >= cutoff - 6 * 3600 and t in (n.get("relatedTickers") or []) and names.search(n.get("title", ""))]
        k = next((n for n in items if KW.search(n.get("title", ""))), items[0] if (mover and items) else None)
        if k: head = k["title"] if len(k["title"]) <= 110 else k["title"][:107] + "…"
    except Exception as e: log("news fail", t, e)
    if mover: why.insert(0, f"Premarket {pct(pm)}" if pm is not None and abs(pm) >= 3 else f"Moved {pct(rm)} last session"); kind = kind or "M"
    if head and (mover or (not why and KW.search(head))): why.append(head); kind = kind or "N"
    return [t, " · ".join(why), kind, 1 if in_list else 0] if why else None
with ThreadPoolExecutor(6) as ex: NEWS = [x for x in ex.map(news_for, U) if x]
order = {"E": 0, "R": 1, "M": 2, "N": 3}
NEWS.sort(key=lambda n: (order[n[2]], -n[3], n[0]))

pre = {r["t"]: PRE[r["t"]] for r in flagged if r["t"] in PRE}
out = dict(asof=asof, session=today, pulled=now_ct.strftime("%a, %b %-d, %-I:%M %p CT"), week=wk, rows=rows, others=others,
           enc2=enc2, pre=pre, news=NEWS[:30])
json.dump(out, open("data.json", "w"), separators=(",", ":"))
json.dump(dict(pulled_utc=dt.datetime.utcnow().isoformat() + "Z", session=today, asof=asof, flagged=len(rows), charts=len(enc2),
               premarket=len(pre), news=len(NEWS), missing=bad), open("status.json", "w"), indent=1)
log(f"ok asof={asof} session={today} flagged={len(rows)} charts={len(enc2)} pre={len(pre)} news={len(NEWS)} missing={bad}")
