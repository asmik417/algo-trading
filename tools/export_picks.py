"""Export a My Picks analysis (a watchlist run) to a formatted Excel workbook.
Reads the running backend over HTTP; nothing here touches the database or the agents' folders.

Usage (from the repo root):
    venv/bin/python tools/export_picks.py                 # latest run of the most recent pick list
    venv/bin/python tools/export_picks.py --run 52        # a specific run id
    venv/bin/python tools/export_picks.py --list 1 --out ~/Desktop/manager_holdings.xlsx
Credentials come from backend/.env (APP_USERNAME / APP_PASSWORD); base URL from --base or API_BASE.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]

VERDICT_FILL = {
    "buy": "D1FAE5", "add": "D1FAE5",
    "watch": "FEF3C7", "hold": "FEF3C7",
    "avoid": "FEE2E2", "exit": "FEE2E2", "trim": "FFEDD5",
}
HEAD_FILL = PatternFill("solid", fgColor="1F2937")
HEAD_FONT = Font(bold=True, color="FFFFFF")
BOLD = Font(bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Side(style="thin", color="E5E7EB")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)


def read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / "backend" / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def rupees(v) -> str:
    if v is None:
        return "—"
    s = f"{abs(v):,.2f}"
    # Indian grouping
    whole, frac = s.split(".")
    whole = whole.replace(",", "")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if v < 0 else "") + "₹" + whole + "." + frac


def pct(v) -> str:
    return "—" if v is None else f"{v:+.1f}%"


def num(v, d=1) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def day(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return iso


def title(s: str | None) -> str:
    return (s or "—").replace("_", " ").title()


class Api:
    def __init__(self, base: str, username: str, password: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        r = self.s.post(f"{self.base}/auth/login", json={"username": username, "password": password}, timeout=30)
        r.raise_for_status()

    def get(self, path: str, **params):
        r = self.s.get(f"{self.base}{path}", params=params or None, timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def style_header(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill, cell.font, cell.alignment, cell.border = HEAD_FILL, HEAD_FONT, Alignment(vertical="center", wrap_text=True), BORDER
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def set_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def verdict_cell(cell, overall: str | None) -> None:
    fill = VERDICT_FILL.get((overall or "").lower())
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    cell.font = BOLD
    cell.alignment = Alignment(horizontal="center", vertical="top")


def build(api: Api, run: dict, items: list[dict], profile: dict, brief: dict | None, out: Path) -> None:
    wb = Workbook()

    # ---------- Sheet 1: Summary ----------
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"{run.get('list_name') or 'My Picks'} — analysis under {profile['name']}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Data as of {day(run.get('trading_day'))} · run #{run['id']} · exported {datetime.now().strftime('%d %b %Y %H:%M')}"
    counts = {"buy": 0, "watch": 0, "avoid": 0}
    for it in items:
        if it.get("verdict"):
            counts[it["verdict"]["overall"]] = counts.get(it["verdict"]["overall"], 0) + 1
    ws["A3"] = f"{len(items)} stocks · {counts['buy']} buy · {counts['watch']} watch · {counts['avoid']} avoid"
    if brief:
        ws["A4"] = f"Market: {title(brief.get('regime'))} — {brief.get('stance', '')}"
        ws["A4"].alignment = WRAP
    ws["A5"] = ("Verdict = what the rules say today. Analyst = the AI analyst's independent reading of the evidence, "
                "audited so every number it quotes exists in the data. Levels and dates come from code, never from the model.")
    ws["A5"].alignment = WRAP
    ws.merge_cells("A5:P5")
    ws.row_dimensions[5].height = 32

    headers = ["#", "Stock", "Cap · Sector", "Verdict", "One-line reason", "Rules passed", "Chart", "Analyst call",
               "Analyst confidence", "Agrees?", "Expectation (next 4 weeks)", "Do not revisit before", "…unless",
               "Price", "Buy zone", "Stop-loss", "Target", "Exit by", "Score", "Signal"]
    hr = 7
    for c, h in enumerate(headers, start=1):
        ws.cell(row=hr, column=c, value=h)
    style_header(ws, hr, len(headers))

    r = hr + 1
    for i, it in enumerate(items, start=1):
        if it.get("error"):
            ws.cell(row=r, column=1, value=i)
            ws.cell(row=r, column=2, value=it["symbol"]).font = BOLD
            ws.cell(row=r, column=5, value=f"Could not analyse: {it['error']}")
            r += 1
            continue
        v, d, a = it["verdict"], it.get("decision") or {}, it.get("analyst")
        exp, rev = d.get("expectation") or {}, d.get("review") or {}
        row = [
            i, it["symbol"], f"{it.get('market_cap_bucket') or '—'} · {it.get('sector') or '—'}",
            title(v["overall"]), d.get("headline") or v.get("reason"),
            f"{v['rules']['passed']}/{v['rules']['total']}", v["chart"]["label"],
            title(a["action"]) if a else "not run", title(a["confidence"]) if a else "—",
            ("Yes" if a["agrees_with_rules"] else "No") if a and a.get("agrees_with_rules") is not None else "—",
            exp.get("text") or "—", day(rev.get("until")), rev.get("trigger") or "—",
            rupees(it.get("price")), rupees(it.get("entry_optimal")), rupees(it.get("stop_loss")), rupees(it.get("target")),
            day(it.get("planned_exit_date")), num(it.get("score"), 0), it.get("signal"),
        ]
        for c, val in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.alignment, cell.border = WRAP, BORDER
        ws.cell(row=r, column=2).font = BOLD
        verdict_cell(ws.cell(row=r, column=4), v["overall"])
        if a:
            verdict_cell(ws.cell(row=r, column=8), a["action"])
        r += 1
    set_widths(ws, [4, 12, 24, 9, 48, 8, 26, 10, 10, 8, 44, 12, 40, 12, 12, 12, 12, 12, 7, 20])

    # ---------- Sheet 2: Reasons ----------
    ws2 = wb.create_sheet("Reasons")
    headers2 = ["Stock", "Verdict", "Evidence FOR", "Evidence AGAINST", "Rules failed", "Chart points",
                "Plain-English summary", "Analyst: what is odd", "Analyst: bull case", "Analyst: bear case",
                "Analyst: trigger that flips the call", "Analyst: wants to know"]
    for c, h in enumerate(headers2, start=1):
        ws2.cell(row=1, column=c, value=h)
    style_header(ws2, 1, len(headers2))
    r = 2
    for it in items:
        if it.get("error"):
            continue
        v, d, a = it["verdict"], it.get("decision") or {}, it.get("analyst")
        finds = d.get("findings") or []
        bullets = lambda xs: "\n".join(f"• {x}" for x in xs) if xs else "—"
        row = [
            it["symbol"], title(v["overall"]),
            bullets([f["text"] for f in finds if f.get("side") == "for"]),
            bullets([f["text"] for f in finds if f.get("side") == "against"]),
            bullets(v["rules"]["failures"]), bullets(v["chart"]["points"]),
            d.get("narrative") or "—",
            bullets(a["anomalies"]) if a else "not run", a["bull_case"] if a else "—", a["bear_case"] if a else "—",
            a["trigger"] if a else "—", a["want_to_know"] if a else "—",
        ]
        for c, val in enumerate(row, start=1):
            cell = ws2.cell(row=r, column=c, value=val)
            cell.alignment, cell.border = WRAP, BORDER
        ws2.cell(row=r, column=1).font = BOLD
        verdict_cell(ws2.cell(row=r, column=2), v["overall"])
        r += 1
    set_widths(ws2, [12, 9, 40, 40, 36, 28, 48, 44, 44, 44, 40, 36])

    # ---------- Sheet 3: Numbers ----------
    ws3 = wb.create_sheet("Numbers")
    headers3 = ["Stock", "Price", "1M %", "3M %", "Volume vs avg", "P/E", "P/B", "ROE %", "Debt/Equity %",
                "Revenue YoY %", "Profit YoY %", "EPS YoY %", "Op. margin %", "Op. cash flow (₹ Cr)", "Market cap (₹ Cr)",
                "RSI", "Trend", "Score", "Stage", "Signal"]
    for c, h in enumerate(headers3, start=1):
        ws3.cell(row=1, column=c, value=h)
    style_header(ws3, 1, len(headers3))
    r = 2
    for it in items:
        if it.get("error"):
            continue
        det = api.get(f"/suggestions/{it['id']}") or {}
        f, ind = det.get("fundamentals") or {}, det.get("indicators") or {}
        mc = f.get("market_cap")
        ocf = f.get("latest_ocf")
        row = [
            it["symbol"], rupees(it.get("price")), pct(it.get("change_1m_pct")), pct(it.get("change_3m_pct")),
            f"{it['volume_ratio_20d']:.1f}x" if it.get("volume_ratio_20d") is not None else "—",
            num(f.get("pe")), num(f.get("pb")), num(f.get("roe_pct")), num(f.get("debt_to_equity"), 0),
            pct(f.get("revenue_yoy_pct")), pct(f.get("profit_yoy_pct")), pct(f.get("eps_yoy_pct")), num(f.get("operating_margin_pct")),
            num(ocf / 1e7, 0) if isinstance(ocf, (int, float)) else "—",
            num(mc / 1e7, 0) if isinstance(mc, (int, float)) else "—",
            num(ind.get("rsi"), 0), ind.get("ema_trend") or "—", num(it.get("score"), 1), it.get("stage"), it.get("signal"),
        ]
        for c, val in enumerate(row, start=1):
            cell = ws3.cell(row=r, column=c, value=val)
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="right" if c > 1 and c < 17 else "left")
        ws3.cell(row=r, column=1).font = BOLD
        r += 1
    set_widths(ws3, [12, 12, 8, 8, 10, 7, 7, 8, 10, 10, 10, 9, 10, 14, 14, 6, 22, 7, 20, 20])

    # ---------- Sheet 4: Market ----------
    if brief:
        ws4 = wb.create_sheet("Market")
        ws4["A1"] = f"Market brief for {day(brief.get('day'))}"
        ws4["A1"].font = Font(bold=True, size=13)
        ws4["A2"] = f"Regime: {title(brief.get('regime'))}"
        ws4["A3"] = f"Stance: {brief.get('stance', '')}"
        ws4["A5"] = "What the numbers say"
        ws4["A5"].font = BOLD
        rr = 6
        for fact in brief.get("facts") or []:
            ws4.cell(row=rr, column=1, value=f"• {fact}")
            rr += 1
        rr += 1
        ws4.cell(row=rr, column=1, value="In plain words").font = BOLD
        ws4.cell(row=rr + 1, column=1, value=brief.get("paragraph") or "").alignment = WRAP
        ws4.merge_cells(start_row=rr + 1, start_column=1, end_row=rr + 1, end_column=1)
        ws4.row_dimensions[rr + 1].height = 90
        ws4.column_dimensions["A"].width = 120

    # ---------- Sheet 5: Disclaimer ----------
    ws5 = wb.create_sheet("Read me")
    lines = [
        "How to read this workbook",
        "",
        "Summary: one row per stock. 'Verdict' is the rules verdict under the named strategy. 'Analyst call' is the AI analyst's "
        "independent reading of the same evidence, with its confidence and whether it agrees with the rules.",
        "Expectation: what we expect over the next 20 trading sessions, with a level and a date, so it can be checked later.",
        "'Do not revisit before … unless …': the review rule. The verdict stands until that date unless the trigger happens.",
        "Reasons: the proof behind every verdict, the plain-English summary, and the analyst's bull case, bear case and trigger.",
        "Numbers: the raw figures the verdict was computed from.",
        "",
        "Every price, level, percentage and date is computed by deterministic code. The language model only writes the text, "
        "and every number it quotes is checked against the data. Paper trading only; nothing here is an order.",
        "Every verdict in this file is logged in the app's Scorecard and graded after 20, 40 and 60 sessions.",
    ]
    for i, line in enumerate(lines, start=1):
        c = ws5.cell(row=i, column=1, value=line)
        c.alignment = WRAP
        if i == 1:
            c.font = Font(bold=True, size=13)
    ws5.column_dimensions["A"].width = 120

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=int, help="watchlist run id (default: latest run of the list)")
    ap.add_argument("--list", type=int, dest="list_id", help="pick list id (default: most recently updated list)")
    ap.add_argument("--profile", type=int, help="strategy id (default: active)")
    ap.add_argument("--base", default=os.getenv("API_BASE", "http://localhost:8000/api/v1"))
    ap.add_argument("--out", help="output .xlsx path (default: exports/<list>_<day>.xlsx)")
    args = ap.parse_args()

    env = read_env()
    api = Api(args.base, env.get("APP_USERNAME", ""), env.get("APP_PASSWORD", ""))

    profile = api.get(f"/profiles/{args.profile}") if args.profile else api.get("/profiles/active")
    if not profile:
        print("No active strategy found", file=sys.stderr)
        return 1

    if args.run:
        results = api.get(f"/runs/{args.run}/results")
    else:
        list_id = args.list_id
        if not list_id:
            lists = api.get("/pick-lists") or []
            if not lists:
                print("No pick lists exist yet", file=sys.stderr)
                return 1
            list_id = lists[0]["id"]
        runs = api.get(f"/profiles/{profile['id']}/watchlist-runs", list_id=list_id, limit=1) or []
        done = [x for x in runs if x["status"] == "done"]
        if not done:
            print(f"No finished analysis for pick list {list_id} under {profile['name']}", file=sys.stderr)
            return 1
        results = api.get(f"/runs/{done[0]['id']}/results")
    if not results:
        print("Run not found", file=sys.stderr)
        return 1

    run, items = results["run"], results["items"]
    # analyst views may be missing on the row for older rows; fetch them directly
    for it in items:
        if it.get("id") and not it.get("analyst"):
            it["analyst"] = api.get(f"/stocks/{it['symbol']}/analyst-view", day=run.get("trading_day"), profile_id=profile["id"])
    brief = api.get("/market/brief", day=run.get("trading_day")) or api.get("/market/brief")

    name = (run.get("list_name") or "my_picks").lower().replace(" ", "_")
    out = Path(args.out) if args.out else ROOT / "exports" / f"{name}_{run.get('trading_day')}.xlsx"
    build(api, run, items, profile, brief, out)
    print(f"Wrote {out}  ({len(items)} stocks, run #{run['id']}, data as of {run.get('trading_day')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
