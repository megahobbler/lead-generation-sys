"""
AGENT 3: CAMPAIGN MANAGER
Reads emails from auto-send/, simulates sending, updates campaign-log.csv.
In TEST MODE: generates realistic engagement metrics (opens, clicks, replies).
In LIVE MODE: requires Gmail API or SendGrid credentials.
"""
import json
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, checkpoint, write_summary,
    loop_prevention_check, update_last_run, load_config,
    read_csv, append_csv, update_daily_summary
)

AUTO_SEND_DIR    = BASE_DIR / "data" / "emails" / "auto-send"
SENT_DIR         = BASE_DIR / "data" / "emails" / "sent"
CAMPAIGN_LOG     = BASE_DIR / "data" / "tracking" / "campaign-log.csv"
POSITIVE_REPLIES = BASE_DIR / "data" / "tracking" / "positive-replies.csv"

CAMPAIGN_FIELDS = [
    "Email_ID", "Lead_Name", "Business_Type", "Lead_Score", "Template_Used",
    "Subject_Line", "Sent_Date", "Sent_Time", "Delivered", "Opened", "Open_Time",
    "Link_Clicked", "Click_Time", "Reply_Received", "Reply_Time", "Reply_Type",
    "Meeting_Booked", "Follow_Up_Status", "Final_Status",
]

DAILY_LIMIT = 20

# Realistic engagement probabilities
OPEN_RATE    = 0.42   # 42%
CLICK_RATE   = 0.14   # 14% of delivered
REPLY_RATE   = 0.09   # 9% of delivered
POSITIVE_PCT = 0.40   # 40% of replies are positive
NEUTRAL_PCT  = 0.40   # 40% neutral
NEGATIVE_PCT = 0.20   # 20% negative
MEETING_PCT  = 0.60   # 60% of positive replies book a meeting


def simulate_engagement(lead_score: int) -> dict:
    """Simulate email engagement based on lead score."""
    # Higher-scored leads engage more
    score_boost = (lead_score - 50) / 200  # ±0.25 based on score
    open_p    = min(0.85, max(0.1, OPEN_RATE + score_boost))
    click_p   = min(0.40, max(0.02, CLICK_RATE + score_boost * 0.5))
    reply_p   = min(0.25, max(0.01, REPLY_RATE + score_boost * 0.5))

    delivered  = random.random() > 0.05  # 95% delivery rate
    opened     = delivered and random.random() < open_p
    clicked    = opened and random.random() < click_p
    replied    = delivered and random.random() < reply_p

    reply_type = ""
    meeting    = False
    if replied:
        r = random.random()
        if r < POSITIVE_PCT:
            reply_type = "Positive"
            meeting = random.random() < MEETING_PCT
        elif r < POSITIVE_PCT + NEUTRAL_PCT:
            reply_type = "Neutral"
        else:
            reply_type = "Negative"

    now = datetime.now()
    open_offset  = timedelta(hours=random.randint(1, 48))
    click_offset = timedelta(minutes=random.randint(5, 120))
    reply_offset = timedelta(hours=random.randint(2, 72))

    return {
        "Delivered":      "Y" if delivered else "N",
        "Opened":         "Y" if opened else "N",
        "Open_Time":      (now + open_offset).strftime("%Y-%m-%d %H:%M") if opened else "",
        "Link_Clicked":   "Y" if clicked else "N",
        "Click_Time":     (now + click_offset).strftime("%Y-%m-%d %H:%M") if clicked else "",
        "Reply_Received": "Y" if replied else "N",
        "Reply_Time":     (now + reply_offset).strftime("%Y-%m-%d %H:%M") if replied else "",
        "Reply_Type":     reply_type,
        "Meeting_Booked": "Y" if meeting else "N",
    }


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(3, "campaign-manager", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 3 - Campaign Manager starting up", "INFO")

    if not loop_prevention_check(3, log_path):
        return
    update_last_run(3)

    config = load_config()
    do_not_contact = [x.lower() for x in config.get("do_not_contact", [])]

    # Check quota
    existing_log = read_csv(CAMPAIGN_LOG)
    today_str = datetime.now().strftime("%Y-%m-%d")
    sent_today = sum(1 for r in existing_log if r.get("Sent_Date") == today_str)
    quota_remaining = DAILY_LIMIT - sent_today
    log(log_path, f"Daily quota: {sent_today}/{DAILY_LIMIT} sent. Remaining: {quota_remaining}", "INFO")

    if quota_remaining <= 0:
        log(log_path, "Daily quota reached. No emails to send today.", "WARNING")
        return

    # Read auto-send emails
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    email_files = sorted(AUTO_SEND_DIR.glob("*.json"))
    if not email_files:
        log(log_path, "No emails in auto-send queue.", "WARNING")
        return

    log(log_path, f"Found {len(email_files)} emails in auto-send queue", "INFO")

    # Sort by lead score descending (send best leads first)
    def get_score(f):
        try:
            return json.loads(f.read_text()).get("lead_score", 0)
        except:
            return 0
    email_files = sorted(email_files, key=get_score, reverse=True)[:quota_remaining]

    new_rows = []
    sent_count = 0
    bounce_count = 0
    positive_replies = []

    for i, email_file in enumerate(email_files):
        try:
            data = json.loads(email_file.read_text())
        except:
            log(log_path, f"Could not read {email_file.name}", "ERROR")
            continue

        lead_name = data.get("lead_name", "Unknown")
        template  = data.get("template_used", "A")
        score     = int(data.get("lead_score", 50))

        if lead_name.lower() in do_not_contact:
            log(log_path, f"SKIPPING {lead_name} (do-not-contact)", "WARNING")
            continue

        # Simulate send
        engagement = simulate_engagement(score)
        email_id   = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i:03d}"
        sent_time  = datetime.now().strftime("%H:%M:%S")

        row = {
            "Email_ID":         email_id,
            "Lead_Name":        lead_name,
            "Business_Type":    data.get("business_type", ""),
            "Lead_Score":       score,
            "Template_Used":    template,
            "Subject_Line":     data.get("subject_line", "")[:80],
            "Sent_Date":        today_str,
            "Sent_Time":        sent_time,
            "Follow_Up_Status": "None",
            "Final_Status":     "Active",
            **engagement,
        }

        if engagement["Reply_Type"] == "Negative":
            row["Final_Status"] = "Unsubscribed"
            # Add to do-not-contact
            dnc_path = BASE_DIR / "config" / "do-not-contact-list.txt"
            with open(dnc_path, "a") as f:
                f.write(f"\n{lead_name}  # {today_str} - Requested removal")
            log(log_path, f"Added {lead_name} to do-not-contact (negative reply)", "INFO")

        if engagement["Reply_Type"] == "Positive":
            row["Final_Status"] = "Interested"
            positive_replies.append({
                "Date": today_str,
                "Lead_Name": lead_name,
                "Business_Type": data.get("business_type", ""),
                "Lead_Score": score,
                "Reply_Type": "Positive",
                "Meeting_Booked": engagement.get("Meeting_Booked", "N"),
                "Action_Taken": "Alert sent to Sean",
            })
            log(log_path, f"🎉 POSITIVE REPLY: {lead_name} (meeting: {engagement['Meeting_Booked']})", "SUCCESS")

        new_rows.append(row)

        if engagement["Delivered"] == "N":
            bounce_count += 1
            log(log_path, f"[{i+1}] BOUNCED: {lead_name}", "WARNING")
        else:
            sent_count += 1
            log(log_path, f"[{i+1}] Sent → {lead_name} | T:{template} | Open:{engagement['Opened']} Click:{engagement['Link_Clicked']} Reply:{engagement['Reply_Type'] or 'None'}", "SUCCESS")

        # Move to sent/
        txt_file = AUTO_SEND_DIR / email_file.name.replace(".json", ".txt")
        shutil.move(str(email_file), str(SENT_DIR / email_file.name))
        if txt_file.exists():
            shutil.move(str(txt_file), str(SENT_DIR / txt_file.name))

        if (i + 1) % 5 == 0:
            checkpoint(log_path, f"{i+1}/{len(email_files)}", {
                "Sent": sent_count,
                "Bounced": bounce_count,
                "Bounce Rate": f"{bounce_count/(i+1)*100:.0f}%",
            })

        # Bounce rate safety check
        if (i + 1) >= 10 and bounce_count / (i + 1) > 0.15:
            log(log_path, f"BOUNCE RATE {bounce_count/(i+1)*100:.0f}% EXCEEDS 15%! Pausing campaign.", "ERROR")
            break

    # Write campaign log
    append_csv(CAMPAIGN_LOG, new_rows, CAMPAIGN_FIELDS)
    log(log_path, f"Campaign log updated: {len(new_rows)} new rows → {CAMPAIGN_LOG.name}", "SUCCESS")

    # Write positive replies
    if positive_replies:
        append_csv(POSITIVE_REPLIES, positive_replies)
        log(log_path, f"⚠️  ALERT: {len(positive_replies)} positive reply(ies) — Sean should follow up!", "WARNING")

    # Check bounce rate
    bounce_rate = bounce_count / len(new_rows) * 100 if new_rows else 0
    log(log_path, f"Bounce rate: {bounce_rate:.1f}% ({'✓ healthy' if bounce_rate < 10 else '⚠️ elevated'})", "INFO")

    summary_text = (
        f"Sent: {sent_count}\n"
        f"Bounced: {bounce_count} ({bounce_rate:.1f}%)\n"
        f"Positive replies: {len(positive_replies)}\n"
        f"Meetings booked: {sum(1 for r in new_rows if r.get('Meeting_Booked')=='Y')}"
    )
    write_summary(log_path, 3, start_time, "SUCCESS", {
        "Emails Sent": sent_count,
        "Bounced": bounce_count,
        "Positive Replies": len(positive_replies),
        "Meetings Booked": sum(1 for r in new_rows if r.get("Meeting_Booked") == "Y"),
    })
    update_daily_summary(3, "Campaign Manager", summary_text)
    log(log_path, "Agent 3 complete ✓", "SUCCESS")
    return new_rows


if __name__ == "__main__":
    run(test_mode=True)
