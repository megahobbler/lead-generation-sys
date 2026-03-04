"""
AGENT 4: ANALYTICS TRACKER
Reads campaign-log.csv and computes daily metrics, A/B test results, and segmentation.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, checkpoint, write_summary,
    loop_prevention_check, update_last_run,
    read_csv, write_csv, update_daily_summary
)

CAMPAIGN_LOG = BASE_DIR / "data" / "tracking" / "campaign-log.csv"
ANALYTICS_DIR = BASE_DIR / "analytics"
AB_DIR = ANALYTICS_DIR / "ab-test-results"

TEMPLATE_NAMES = {"A": "Problem-Focused", "B": "Proof-Focused", "C": "Voice Quality", "D": "Risk-Free"}


def safe_rate(num, den):
    return round(num / den * 100, 1) if den > 0 else 0


def confidence(n):
    if n >= 100: return "High"
    if n >= 50:  return "Medium"
    if n >= 20:  return "Low"
    return "Insufficient Data"


def analyze(rows: list) -> dict:
    total   = len(rows)
    deliv   = sum(1 for r in rows if r.get("Delivered") == "Y")
    opened  = sum(1 for r in rows if r.get("Opened") == "Y")
    clicked = sum(1 for r in rows if r.get("Link_Clicked") == "Y")
    replied = sum(1 for r in rows if r.get("Reply_Received") == "Y")
    pos     = sum(1 for r in rows if r.get("Reply_Type") == "Positive")
    meetings= sum(1 for r in rows if r.get("Meeting_Booked") == "Y")
    return {
        "sent": total, "delivered": deliv,
        "delivery_rate": safe_rate(deliv, total),
        "opens": opened, "open_rate": safe_rate(opened, deliv),
        "clicks": clicked, "click_rate": safe_rate(clicked, deliv),
        "replies": replied, "reply_rate": safe_rate(replied, deliv),
        "positive": pos, "positive_rate": safe_rate(pos, deliv),
        "meetings": meetings, "meeting_rate": safe_rate(meetings, deliv),
    }


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(4, "analytics-tracker", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 4 - Analytics Tracker starting up", "INFO")

    if not loop_prevention_check(4, log_path):
        return
    update_last_run(4)

    rows = read_csv(CAMPAIGN_LOG)
    if not rows:
        log(log_path, "No campaign data found. Run Agent 3 first.", "ERROR")
        return

    log(log_path, f"Loaded {len(rows)} campaign records", "SUCCESS")
    today = datetime.now().strftime("%Y-%m-%d")

    # ── Daily metrics ──────────────────────────────────────────────────────
    today_rows = [r for r in rows if r.get("Sent_Date") == today]
    total_stats = analyze(rows)
    today_stats = analyze(today_rows)
    log(log_path, f"Today: {today_stats['sent']} sent | {today_stats['open_rate']}% open | {today_stats['reply_rate']}% reply", "SUCCESS")

    daily_row = {
        "Date": today,
        "Emails_Sent": today_stats["sent"],
        "Delivered": today_stats["delivered"],
        "Delivery_Rate": f"{today_stats['delivery_rate']}%",
        "Opens": today_stats["opens"],
        "Open_Rate": f"{today_stats['open_rate']}%",
        "Clicks": today_stats["clicks"],
        "Click_Rate": f"{today_stats['click_rate']}%",
        "Replies": today_stats["replies"],
        "Reply_Rate": f"{today_stats['reply_rate']}%",
        "Positive_Replies": today_stats["positive"],
        "Positive_Rate": f"{today_stats['positive_rate']}%",
        "Meetings": today_stats["meetings"],
        "Meeting_Rate": f"{today_stats['meeting_rate']}%",
    }
    write_csv(ANALYTICS_DIR / f"daily-performance-{today}.csv", [daily_row])
    log(log_path, f"Saved daily performance → daily-performance-{today}.csv", "SUCCESS")

    # ── A/B test analysis ──────────────────────────────────────────────────
    checkpoint(log_path, "A/B test analysis", {"Total records": len(rows)})
    ab_rows = []
    for t in ["A", "B", "C", "D"]:
        t_rows = [r for r in rows if r.get("Template_Used") == t]
        stats  = analyze(t_rows)
        conf   = confidence(stats["sent"])
        ab_rows.append({
            "Template": t,
            "Name": TEMPLATE_NAMES[t],
            "Sample_Size": stats["sent"],
            "Open_Rate": f"{stats['open_rate']}%",
            "Click_Rate": f"{stats['click_rate']}%",
            "Reply_Rate": f"{stats['reply_rate']}%",
            "Positive_Rate": f"{stats['positive_rate']}%",
            "Meeting_Rate": f"{stats['meeting_rate']}%",
            "Confidence": conf,
        })
        log(log_path, f"Template {t} (n={stats['sent']}): Open={stats['open_rate']}% Reply={stats['reply_rate']}% [{conf}]", "INFO")

    AB_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(AB_DIR / f"weekly-{today}.csv", ab_rows)
    log(log_path, f"Saved A/B test results → weekly-{today}.csv", "SUCCESS")

    # ── Segment analysis ───────────────────────────────────────────────────
    seg_rows = []

    # By business type
    for btype in set(r.get("Business_Type", "") for r in rows if r.get("Business_Type")):
        s = analyze([r for r in rows if r.get("Business_Type") == btype])
        seg_rows.append({"Segment": "Business_Type", "Category": btype,
                         "Emails_Sent": s["sent"], "Open_Rate": f"{s['open_rate']}%",
                         "Reply_Rate": f"{s['reply_rate']}%", "Positive_Rate": f"{s['positive_rate']}%"})

    # By lead score bucket
    for label, lo, hi in [("High (75-100)", 75, 100), ("Medium (50-74)", 50, 74), ("Low (30-49)", 30, 49)]:
        subset = [r for r in rows if lo <= int(r.get("Lead_Score", 0) or 0) <= hi]
        s = analyze(subset)
        seg_rows.append({"Segment": "Lead_Score", "Category": label,
                         "Emails_Sent": s["sent"], "Open_Rate": f"{s['open_rate']}%",
                         "Reply_Rate": f"{s['reply_rate']}%", "Positive_Rate": f"{s['positive_rate']}%"})

    # By day of week
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        subset = [r for r in rows if r.get("Sent_Date") and
                  datetime.strptime(r["Sent_Date"], "%Y-%m-%d").strftime("%A") == day]
        s = analyze(subset)
        if s["sent"] > 0:
            seg_rows.append({"Segment": "Day", "Category": day,
                             "Emails_Sent": s["sent"], "Open_Rate": f"{s['open_rate']}%",
                             "Reply_Rate": f"{s['reply_rate']}%", "Positive_Rate": f"{s['positive_rate']}%"})

    write_csv(ANALYTICS_DIR / f"segment-analysis-{today}.csv", seg_rows)
    log(log_path, f"Saved segment analysis → segment-analysis-{today}.csv", "SUCCESS")

    summary_text = (
        f"Records analyzed: {len(rows)}\n"
        f"Overall open rate: {total_stats['open_rate']}%\n"
        f"Overall reply rate: {total_stats['reply_rate']}%\n"
        f"Meetings booked: {total_stats['meetings']}\n"
        f"Best template (by reply rate): {max(ab_rows, key=lambda x: float(x['Reply_Rate'].rstrip('%')))['Template']}"
    )
    write_summary(log_path, 4, start_time, "SUCCESS", {
        "Records Analyzed": len(rows),
        "Open Rate": f"{total_stats['open_rate']}%",
        "Reply Rate": f"{total_stats['reply_rate']}%",
        "Meetings": total_stats["meetings"],
    })
    update_daily_summary(4, "Analytics Tracker", summary_text)
    log(log_path, "Agent 4 complete ✓", "SUCCESS")
    return total_stats


if __name__ == "__main__":
    run(test_mode=True)
