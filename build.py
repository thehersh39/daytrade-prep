#!/usr/bin/env python3
"""Build the Morning Day-Trade Prep page and email from the browser scan.
Usage: python3 build.py data.json template.txt index.html email.html
Defaults mirror the page: 1.5-pt max stop, $100 risk/trade, $300 lockout, $200K buying power."""
import json, sys, math, html
data_p, tpl_p, page_p, mail_p = sys.argv[1:5]
D = json.load(open(data_p))
tpl = open(tpl_p).read()
assert '__DATA__' in tpl
open(page_p, 'w').write(tpl.replace('__DATA__', json.dumps(D, separators=(',', ':'))))

MAXSTOP, RISK, LOCK, BP = 1.5, 100, 300, 200000
DN = dict(D['week'])
PRE = D.get('pre', {})
rows = []
for r in D['rows']:
    a = r.split('|'); N = lambda i: float(a[i])
    rows.append(dict(t=a[0], c=N(1), chg=N(2), atr=N(3), h=N(7), l=N(8), h5=N(9), l5=N(10), h90=N(11), l90=N(12),
                     s20=N(13), s50=N(14), tags=a[16].split('/'), bias=int(float(a[17])), trend=int(float(a[18])), ewk=a[19], sc=N(20)))
def calc(r):
    stop = max(0.05, min(MAXSTOP, round(0.25 * r['atr'], 2))); ratio = stop / r['atr']
    fit = 'Good fit' if ratio >= 0.249 else 'Tight' if ratio >= 0.15 else 'Too volatile'
    sh = max(0, min(math.floor(RISK / stop), math.floor(BP / r['c'])))
    tick = 0.05 if r['c'] >= 100 else 0.02
    lt = round(r['h'] + tick, 2); stt = round(r['l'] - tick, 2)
    dirs = ['long'] if r['bias'] > 0 else ['short'] if r['bias'] < 0 else (['long', 'short'] if r['trend'] >= 0 else ['short', 'long'])
    return dict(stop=stop, fit=fit, sh=sh, dirs=dirs,
                long=(lt, round(lt - stop, 2), round(lt + 2 * stop, 2)), short=(stt, round(stt + stop, 2), round(stt - 2 * stop, 2)))
rank = {'Good fit': 0, 'Tight': 1, 'Too volatile': 2}
R = sorted([(r, calc(r)) for r in rows], key=lambda x: (rank[x[1]['fit']], -x[0]['sc']))
best = [x for x in R if x[1]['fit'] != 'Too volatile'][:14]
f2 = lambda v: f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}"
G, Rd, M, INK, LINE = '#16805B', '#BF3A31', '#5C6A6E', '#1B2327', '#D2D9D5'
td = f'padding:6px 8px;border-bottom:1px solid {LINE};font-family:Menlo,Consolas,monospace;font-size:13px;white-space:nowrap;'
th = f'padding:6px 8px;border-bottom:2px solid {INK};font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:{M};text-align:left;white-space:nowrap;'
trs = []
for r, k in best:
    pre = PRE.get(r['t']); note = ''
    if pre and pre > k['long'][0]: note = f'<br><span style="color:#9A6A12">Premarket {f2(pre)} is above the long trigger. Don\'t chase.</span>'
    if pre and pre < k['short'][0]: note = f'<br><span style="color:#9A6A12">Premarket {f2(pre)} is below the short trigger. Don\'t chase.</span>'
    plans = []
    for d in k['dirs']:
        tr, st, t2 = k[d]; col = G if d == 'long' else Rd
        plans.append(f'<span style="color:{col};font-weight:bold">{"Long over" if d=="long" else "Short under"} {f2(tr)}</span> stop {f2(st)} · 2R {f2(t2)}')
    earn = f'<br><span style="color:#9A6A12">Earnings {DN.get(r["ewk"], r["ewk"])}</span>' if r['ewk'] else ''
    trs.append(f'<tr><td style="{td}font-weight:bold">{r["t"]}</td><td style="{td}font-family:Arial,sans-serif">{html.escape(", ".join(r["tags"]))}<br><span style="color:{M}">{k["fit"]} · ATR {f2(r["atr"])}</span>{earn}</td>'
               f'<td style="{td}">{f2(r["c"])}{"<br>Pre "+f2(pre) if pre else ""}</td><td style="{td}">{"<br>".join(plans)}{note}</td><td style="{td}">{k["stop"]:.2f} pts<br>{k["sh"]} sh · ${k["sh"]*k["stop"]:.0f}</td></tr>')
allE = {}
for r in D['rows']:
    a = r.split('|')
    if a[19]: allE.setdefault(a[19], []).append(a[0])
for r in D['others']:
    a = r.split(',')
    if len(a) > 4 and a[4]: allE.setdefault(a[4], []).append(a[0])
earn_line = ' · '.join(f'<b>{DN[d]}</b> {" ".join(sorted(allE[d]))}' for d, _ in D['week'] if d in allE) or 'None on the list this week.'
asof = D['asof']; MO = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
asof_txt = f"{MO[int(asof[4:6])-1]} {int(asof[6:])}"
page_url = sys.argv[5] if len(sys.argv) > 5 else ''
NEWS = D.get('news', [])
news_html = ''.join(f'<tr><td style="{td}font-weight:bold;vertical-align:top">{html.escape(n[0])}</td><td style="{td}font-family:Arial,sans-serif;white-space:normal">{html.escape(n[1])}</td></tr>' for n in NEWS)
news_block = (f'<h3 style="margin:18px 0 4px;font-family:Georgia,serif">In play on news</h3><p style="font-size:12px;color:{M};margin:0 0 6px">Earnings, rating changes since the last close, and names moving 3%+ premarket or 5%+ last session with a headline.</p><table style="border-collapse:collapse;width:100%">{news_html}</table>') if NEWS else ''
mail = f'''<div style="font-family:Arial,Helvetica,sans-serif;color:{INK};max-width:760px">
<h2 style="margin:0 0 4px;font-family:Georgia,serif">Day-trade prep for {DN[D['week'][0][0]]}</h2>
<p style="margin:0 0 12px;color:{M};font-size:13px">Levels from the {asof_txt} close · pulled {html.escape(D['pulled'])} · 1.5-pt max stop, $100 risk per trade, 3 losses to the $300 lockout</p>
<p style="font-size:14px;margin:0 0 6px"><b>Earnings this week:</b> {earn_line}</p>
<p style="font-size:13px;margin:0 0 12px;color:{M}">Wait for the first 5–15 minutes. Take a trigger only on a 1- or 5-minute candle that breaks and holds. Skip anything that has already gapped past its trigger.</p>
{news_block}<h3 style="margin:18px 0 4px;font-family:Georgia,serif">Tight-stop setups</h3><table style="border-collapse:collapse;width:100%"><tr><th style="{th}">Ticker</th><th style="{th}">Setup</th><th style="{th}">Close</th><th style="{th}">Plan</th><th style="{th}">Size</th></tr>{''.join(trs)}</table>
{f'<p style="font-size:14px;margin:16px 0 0"><a href="{page_url}" style="color:#2F4F86">Open the full page with charts and all {len(rows)} flagged names</a> (opens only on the account that owns it)</p>' if page_url else ''}
<p style="font-size:11px;color:{M};margin-top:16px">Rules-based screen from Yahoo Finance data; news items are headlines and analyst actions from Yahoo, so confirm before trading. No read on futures. Fills can slip past a stop in a fast market. Educational only, not financial advice.</p></div>'''
open(mail_p, 'w').write(mail)
# Plain-text fallback next to the HTML email
lines = [f"Day-trade prep for {DN[D['week'][0][0]]} (levels from the {asof_txt} close)", ""]
if NEWS:
    lines += ["IN PLAY ON NEWS"] + [f"{n[0]}: {n[1]}" for n in NEWS] + [""]
lines.append("TIGHT-STOP SETUPS (1.5-pt max stop, $100 risk)")
for r, k in best:
    for d in k['dirs']:
        tr, st, t2 = k[d]
        lines.append(f"{r['t']}: {'long over' if d=='long' else 'short under'} {f2(tr)} stop {f2(st)} 2R {f2(t2)} ({k['sh']} sh)")
if page_url: lines += ["", f"Full page: {page_url}"]
open(mail_p.rsplit('.', 1)[0] + '.txt', 'w').write("\n".join(lines) + "\n")
print(f"page ok, email ok: {len(best)} names, {len(rows)} flagged, asof {asof}, session {D['session']}, premarket {len(PRE)}")
