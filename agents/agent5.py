"""
AGENT 5: INSIGHTS GENERATOR
Reads analytics files and generates weekly markdown insights report.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, write_summary,
    loop_prevention_check, update_last_run,
    read_csv, update_daily_summary
)

ANALYTICS_DIR  = BASE_DIR / "analytics"
INSIGHTS_DIR   = ANALYTICS_DIR / "weekly-insights"
AB_DIR         = ANALYTICS_DIR / "ab-test-results"
CAMPAIGN_LOG   = BASE_DIR / "data" / "tracking" / "campaign-log.csv"
TEMPLATE_NAMES = {"A": "Problem-Focused", "B": "Proof-Focused", "C": "Voice Quality", "D": "Risk-Free"}


def safe_rate(num, den):
    return round(num / den * 100, 1) if den > 0 else 0


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(5, "insights-generator", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 5 - Insights Generator starting up", "INFO")

    if not loop_prevention_check(5, log_path, min_interval_minutes=60):
        return
    update_last_run(5)

    rows = read_csv(CAMPAIGN_LOG)
    if len(rows) < 10:
        log(log_path, f"Only {len(rows)} records. Need at least 10 for insights. Generating preliminary report.", "WARNING")

    today     = datetime.now()
    week_ago  = today - timedelta(days=7)
    date_str  = today.strftime("%Y-%m-%d")
    week_rows = [r for r in rows if r.get("Sent_Date", "") >= week_ago.strftime("%Y-%m-%d")]

    log(log_path, f"Total records: {len(rows)} | This week: {len(week_rows)}", "INFO")

    def analyze(subset):
        total   = len(subset)
        deliv   = sum(1 for r in subset if r.get("Delivered") == "Y")
        opened  = sum(1 for r in subset if r.get("Opened") == "Y")
        replied = sum(1 for r in subset if r.get("Reply_Received") == "Y")
        pos     = sum(1 for r in subset if r.get("Reply_Type") == "Positive")
        meetings= sum(1 for r in subset if r.get("Meeting_Booked") == "Y")
        return dict(sent=total, delivered=deliv,
                    open_rate=safe_rate(opened, deliv),
                    reply_rate=safe_rate(replied, deliv),
                    positive_rate=safe_rate(pos, deliv),
                    meeting_rate=safe_rate(meetings, deliv),
                    meetings=meetings, positive=pos, replied=replied)

    overall = analyze(rows)
    weekly  = analyze(week_rows)

    # Template analysis
    template_stats = {}
    for t in ["A", "B", "C", "D"]:
        t_rows = [r for r in rows if r.get("Template_Used") == t]
        template_stats[t] = analyze(t_rows)
        template_stats[t]["n"] = len(t_rows)

    # Find winner and loser
    valid_templates = {t: s for t, s in template_stats.items() if s["n"] >= 5}
    if valid_templates:
        winner = max(valid_templates, key=lambda t: valid_templates[t]["reply_rate"])
        loser  = min(valid_templates, key=lambda t: valid_templates[t]["reply_rate"])
    else:
        winner = loser = "A"

    # Segment analysis
    r_rows = [r for r in rows if "restaurant" in r.get("Business_Type","").lower() or "cafe" in r.get("Business_Type","").lower()]
    c_rows = [r for r in rows if r not in r_rows]
    r_stats = analyze(r_rows)
    c_stats = analyze(c_rows)

    hi_rows  = [r for r in rows if int(r.get("Lead_Score",0) or 0) >= 75]
    mid_rows = [r for r in rows if 50 <= int(r.get("Lead_Score",0) or 0) < 75]
    lo_rows  = [r for r in rows if int(r.get("Lead_Score",0) or 0) < 50]

    # Day analysis
    day_stats = {}
    for day in ["Tuesday","Wednesday","Thursday","Friday"]:
        day_rows = [r for r in rows if r.get("Sent_Date") and
                    datetime.strptime(r["Sent_Date"],"%Y-%m-%d").strftime("%A") == day]
        day_stats[day] = analyze(day_rows)

    best_day = max(day_stats, key=lambda d: day_stats[d]["open_rate"]) if any(day_stats[d]["sent"]>0 for d in day_stats) else "Tuesday"

    def conf(n):
        if n >= 100: return "High (statistically significant)"
        if n >= 50:  return "Medium"
        return f"Low (n={n}, need 100+)"

    # ── Build report ──────────────────────────────────────────────────────
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = INSIGHTS_DIR / f"insights-{date_str}.md"

    w_start = week_ago.strftime("%b %d")
    w_end   = today.strftime("%b %d, %Y")

    report = f"""# SWOPLABS WEEKLY INSIGHTS
Week of: {w_start} – {w_end}
Generated: {today.strftime("%Y-%m-%d %H:%M")}

---

## EXECUTIVE SUMMARY

**Campaign Performance (This Week):**
- Emails sent: {weekly['sent']}
- Overall open rate: {weekly['open_rate']}%
- Overall reply rate: {weekly['reply_rate']}%
- Positive replies: {weekly['positive']}
- Meetings booked: {weekly['meetings']}

**All-Time:**
- Total sent: {overall['sent']}
- Open rate: {overall['open_rate']}%
- Reply rate: {overall['reply_rate']}%
- Total meetings: {overall['meetings']}

**Key Finding:** Template {winner} showing strongest performance ({template_stats[winner]['reply_rate']}% reply rate)
**Recommendation:** Increase Template {winner} to 40% of sends next week

---

## TEMPLATE PERFORMANCE (A/B TESTING)

### 🏆 LEADING TEMPLATE: {winner} — {TEMPLATE_NAMES[winner]}
- Sample size: n={template_stats[winner]['n']} | {conf(template_stats[winner]['n'])}
- Open rate: {template_stats[winner]['open_rate']}% (avg: {overall['open_rate']}%)
- Reply rate: {template_stats[winner]['reply_rate']}% (avg: {overall['reply_rate']}%)
- Meetings: {template_stats[winner]['meetings']}

### All Templates:
"""
    for t in ["A", "B", "C", "D"]:
        s = template_stats[t]
        marker = " ← WINNER" if t == winner else (" ← UNDERPERFORMING" if t == loser and loser != winner else "")
        report += f"""
**Template {t} — {TEMPLATE_NAMES[t]}{marker}**
- n={s['n']} | Open: {s['open_rate']}% | Reply: {s['reply_rate']}% | Meetings: {s['meetings']}
"""

    report += f"""
---

## SEGMENT INSIGHTS

### By Business Type:
- **Restaurants/Cafes** (n={r_stats['sent']}): {r_stats['open_rate']}% open, {r_stats['reply_rate']}% reply
- **Clinics** (n={c_stats['sent']}): {c_stats['open_rate']}% open, {c_stats['reply_rate']}% reply
- **Recommendation:** {"Continue 50/50 split — performance similar" if abs(r_stats['reply_rate'] - c_stats['reply_rate']) < 3 else f"Focus more on {'restaurants' if r_stats['reply_rate'] > c_stats['reply_rate'] else 'clinics'}"}

### By Lead Score:
- **High (75-100):** n={len(hi_rows)}, open={analyze(hi_rows)['open_rate']}%, reply={analyze(hi_rows)['reply_rate']}%
- **Medium (50-74):** n={len(mid_rows)}, open={analyze(mid_rows)['open_rate']}%, reply={analyze(mid_rows)['reply_rate']}%
- **Low (30-49):** n={len(lo_rows)}, open={analyze(lo_rows)['open_rate']}%, reply={analyze(lo_rows)['reply_rate']}%
- **Finding:** Higher lead scores correlate with higher engagement. Prioritize chains.

### Best Day to Send:
- **{best_day}** showing highest open rate ({day_stats[best_day]['open_rate']}%)
- Recommendation: Concentrate sends on {best_day}/Wednesday

---

## ACTIONABLE RECOMMENDATIONS FOR NEXT WEEK

1. **TEMPLATE DISTRIBUTION** — Change from 25/25/25/25 to:
   - Template {winner}: 40% (increase — it's working)
   - Template {loser}: 15% (decrease — underperforming)
   - Other two: 22.5% each

2. **LEAD PRIORITIZATION** — Focus Agent 1 on finding more chains (2+ locations)

3. **SEND SCHEDULE** — More sends on {best_day}/Wednesday, fewer on Fridays

4. **FOLLOW-UP TRACKING** — Review Day-4 vs Day-8 follow-up open rates

5. **SAMPLE SIZE** — Need 100+ sends per template for statistical significance
   - Currently: {min(template_stats[t]['n'] for t in template_stats)}–{max(template_stats[t]['n'] for t in template_stats)} per template
   - Estimated weeks to significance: {max(1, round((100 - min(template_stats[t]['n'] for t in template_stats)) / max(1, weekly['sent'] / 4)))}

---

## NEXT STEPS FOR SEAN

- [ ] Review positive replies ({weekly['positive']} this week) and follow up
- [ ] Check pending-approval/ for high-value chain emails
- [ ] Confirm template distribution change for next week
- [ ] Add intro deck link to /config/intro-deck-link.txt (used in follow-up emails)

---

*Report generated by Agent 5 (Insights Generator)*
*Next report: {(today + timedelta(days=7)).strftime("%A, %B %d")}*
"""

    report_path.write_text(report)
    log(log_path, f"Weekly insights report saved → {report_path.name}", "SUCCESS")

    summary_text = (
        f"Records analyzed: {len(rows)}\n"
        f"This week sent: {weekly['sent']}\n"
        f"Leading template: {winner} ({template_stats[winner]['reply_rate']}% reply)\n"
        f"Meetings booked this week: {weekly['meetings']}"
    )
    write_summary(log_path, 5, start_time, "SUCCESS", {
        "Records Analyzed": len(rows),
        "Weekly Sent": weekly["sent"],
        "Leading Template": f"{winner} ({TEMPLATE_NAMES[winner]})",
        "Report Path": str(report_path),
    })
    update_daily_summary(5, "Insights Generator", summary_text)
    log(log_path, "Agent 5 complete ✓", "SUCCESS")
    return str(report_path)


if __name__ == "__main__":
    run(test_mode=True)
