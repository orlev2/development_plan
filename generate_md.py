#!/usr/bin/env python3
"""
Generate a Markdown snapshot from data.json.
Run directly or via the pre-commit git hook / serve.py POST /save.
"""

import json, os, sys
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    os.system(f"{sys.executable} -m pip install beautifulsoup4 -q")
    from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(SCRIPT_DIR, "data.json")
MD_FILE    = os.path.join(SCRIPT_DIR, "development_plan.md")

STATUS_PCT = {"Not Started": 5, "Started": 25, "In Progress": 50, "Done": 100, "Blocked": 10}

def txt(el): return el.get_text(strip=True) if el else "—"
def val(el): return (el.get("value") or "").strip() if el else "—"

def generate():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    employee = data.get("employee", "—")
    manager  = data.get("manager",  "—")
    period   = data.get("period",   "—")
    cur_lvl  = data.get("curLevel", "—")
    tgt_lvl  = data.get("tgtLevel", "—")
    rev_date = data.get("revDate",  "—")
    dims     = {d["id"]: d["label"] for d in data.get("dims", [])}

    # Parse action rows from stored HTML fragment
    action_rows = []
    action_soup = BeautifulSoup(data.get("actionHTML", ""), "html.parser")
    for tr in action_soup.find_all("tr"):
        classes = tr.get("class", [])
        if "subtask-row" in classes or "subtask-add-row" in classes:
            continue
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue
        dim_id    = tr.get("data-dim", "")
        dim_label = dims.get(dim_id, dim_id or "—")
        action_rows.append({
            "action":   tds[1].get_text(strip=True),
            "type":     tds[2].get_text(strip=True),
            "dim":      dim_label,
            "owner":    tds[4].get_text(strip=True),
            "due":      val(tds[5].find("input")) if tds[5].find("input") else tds[5].get_text(strip=True),
            "priority": tds[6].get_text(strip=True),
            "status":   tds[7].get_text(strip=True),
            "comment":  (tds[8].find("textarea").get_text(strip=True) if len(tds) > 8 and tds[8].find("textarea") else "").replace("\n", " "),
        })

    # Parse notes
    notes = []
    notes_soup = BeautifulSoup(data.get("notesHTML", ""), "html.parser")
    for tr in notes_soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 3: continue
        note_date = val(tds[0].find("input")) if tds[0].find("input") else tds[0].get_text(strip=True)
        note_type = tds[1].get_text(strip=True)
        if "auto-log-row" in tr.get("class", []):
            items = [li.get_text(strip=True) for li in tds[2].find_all("li")]
            notes.append({"date": note_date, "type": "Auto", "text": "; ".join(items)})
        else:
            ta = tds[2].find("textarea")
            text = (ta.get_text(strip=True) if ta else tds[2].get_text(strip=True)).replace("\n", " ")
            if text:
                notes.append({"date": note_date, "type": note_type, "text": text})

    # Overall readiness
    pcts = [STATUS_PCT.get(r["status"], 5) for r in action_rows]
    overall = round(sum(pcts) / len(pcts)) if pcts else 0
    if overall >= 90:   readiness = "🟢 Ready to promote"
    elif overall >= 65: readiness = "🔵 On track"
    elif overall >= 35: readiness = "🟡 Progress made"
    else:               readiness = "🔴 Significant gaps remain"

    # Dimension summary
    dim_stats = {}
    for r in action_rows:
        k = r["dim"]
        if k not in dim_stats: dim_stats[k] = {"total": 0, "done": 0, "pct": 0}
        dim_stats[k]["total"] += 1
        dim_stats[k]["pct"]   += STATUS_PCT.get(r["status"], 5)
        if r["status"] == "Done": dim_stats[k]["done"] += 1

    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Development Plan — {employee}",
        f"",
        f"> **Generated:** {generated} &nbsp;|&nbsp; **Period:** {period}",
        f"",
        f"| | |",
        f"|---|---|",
        f"| **Employee** | {employee} |",
        f"| **Manager** | {manager} |",
        f"| **Current Level** | {cur_lvl} |",
        f"| **Target Level** | {tgt_lvl} |",
        f"| **Review Date** | {rev_date} |",
        f"| **Overall Readiness** | {overall}% — {readiness} |",
        f"",
        f"---",
        f"",
        f"## 📊 Overview",
        f"",
        f"| Dimension | Done | Progress | Status |",
        f"|---|---|---|---|",
    ]
    for dim, s in dim_stats.items():
        avg = round(s["pct"] / s["total"]) if s["total"] else 0
        bar = ("█" * (avg // 10)).ljust(10)
        st = "Done" if avg >= 90 else ("In Progress" if avg >= 50 else ("Started" if avg >= 20 else "Not Started"))
        lines.append(f"| {dim} | {s['done']}/{s['total']} | `{bar}` {avg}% | {st} |")

    lines += ["", "---", "", "## 🗓 Action Plan", "",
              "| # | Action | Type | Dimension | Owner | Due | Priority | Status | Comments |",
              "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(action_rows, 1):
        a = r["action"][:80] + ("…" if len(r["action"]) > 80 else "")
        c = r["comment"][:60] + ("…" if len(r["comment"]) > 60 else "") if r["comment"] else ""
        lines.append(f"| {i} | {a} | {r['type']} | {r['dim']} | {r['owner']} | {r['due']} | {r['priority']} | {r['status']} | {c} |")

    lines += ["", "---", "", "## 📝 Notes & Log", ""]
    for n in notes:
        lines += [f"**{n['date']}** &nbsp; `{n['type']}`", f"> {n['text']}", ""]

    lines += ["---", "", "_Auto-generated from `data.json` — do not edit manually._"]

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✅  {os.path.basename(MD_FILE)} updated ({len(action_rows)} actions, {len(notes)} notes)")

if __name__ == "__main__":
    generate()
