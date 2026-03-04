"""
AGENT 2: EMAIL WRITER
Reads today's leads and writes personalized cold emails.
4 A/B test templates, auto-assigned in rotation.
High-score leads (≥75) go to pending-approval/, others to auto-send/.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, checkpoint, write_summary,
    loop_prevention_check, update_last_run, load_config,
    read_csv, write_csv, append_csv, update_daily_summary
)

AUTO_SEND_DIR    = BASE_DIR / "data" / "emails" / "auto-send"
APPROVAL_DIR     = BASE_DIR / "data" / "emails" / "pending-approval"
ASSIGNMENTS_FILE = BASE_DIR / "data" / "tracking" / "template-assignments.csv"
ASSIGNMENTS_FIELDS = ["Lead_Name", "Business_Type", "Lead_Score", "Template_Assigned", "Date_Assigned"]

TEMPLATE_NAMES = {"A": "Problem-Focused", "B": "Proof-Focused", "C": "Voice Quality", "D": "Risk-Free"}
TEMPLATE_ORDER = ["A", "B", "C", "D"]

# ─── TEMPLATES ────────────────────────────────────────────────────────────────

def build_email(lead: dict, template: str, config: dict) -> tuple[str, str]:
    """Returns (subject, body) for the given lead and template."""
    name        = lead["Business_Name"]
    btype       = lead["Business_Type"]
    is_clinic   = "clinic" in btype.lower() or btype in ("GP_Clinic","Dental","Aesthetics","Specialist","TCM","Physiotherapy")
    neighborhood = lead.get("Neighborhood", "Singapore")
    locations   = int(lead.get("Number_of_Locations", 1))
    calendar    = config.get("calendar_link") or "https://calendly.com/sean-tan-swoplabs/30min"
    sig = f"""Best,
Sean Tan
SWOPLABS.AI
linkedin.com/in/sean-tan-961903247
+65 83289068
sean.tan@swoplabs.app"""

    # Clinic language substitutions
    booking_word = "appointments" if is_clinic else "bookings"
    rush_phrase  = "peak hours" if is_clinic else "dinner rush"
    biz_word     = "clinic" if is_clinic else "restaurant"
    ps_word      = "a patient books elsewhere" if is_clinic else "you money"
    hi_name      = f"Dr. {name.split()[0]}" if is_clinic and lead.get("Decision_Maker_Name","Not Found") == "Not Found" else "there"
    chain_str    = f" across your {locations} locations" if locations > 1 else ""

    if template == "A":
        subject = f"{name} - $27K lost to missed calls?"
        body = f"""Hi {hi_name},

Quick reality check: Singapore {biz_word}s lose an average of $27,000/year from unanswered calls during peak hours.

69% of customers won't call back if you don't answer - they just book your competitor instead.

We're piloting an AI phone system with F&B groups in Singapore and Jakarta that answers 100% of calls{chain_str}, even when you're slammed.

Unlike robotic AI you've heard before, ours sounds like an actual human - we can even clone your best staff member's voice.

2-week free trial?
{calendar}

{sig}

Reply 'unsubscribe' to opt out."""

    elif template == "B":
        subject = f"{name} - see how we helped similar {biz_word}s"
        body = f"""Hi {hi_name},

We're currently piloting an AI phone system with {biz_word} groups across Singapore and Jakarta.

The results: {biz_word}s capturing 43% more {booking_word} (calls they used to miss during {rush_phrase}).

What makes it different:
- Sounds like a real human (not robotic AI)
- Handles English, Mandarin, Malay, Bahasa
- Built by SMU & Columbia grads who get Singapore F&B

Currently helping {btype} businesses in {neighborhood} - thought you'd be a great fit{chain_str}.

15-min demo or 2-week free trial?
{calendar}

{sig}

P.S. - 99.9% uptime. Because a missed call costs {ps_word}.

Reply 'unsubscribe' to opt out."""

    elif template == "C":
        subject = f"{name} - AI that sounds human?"
        body = f"""Hi {hi_name},

Honest question: have you tried AI phone systems before and hated how robotic they sound?

We built something different. Our AI sounds like an actual person - we can even clone your best staff member's voice.

Currently piloting with Singapore and Jakarta {biz_word}s{chain_str} who were skeptical but became believers after hearing it.

Want to try it free for 2 weeks? Zero setup time.
{calendar}

{sig}

Built by SMU & Columbia grads. Singapore-made for Singapore {biz_word}s.

Reply 'unsubscribe' to opt out."""

    else:  # D
        subject = f"{name} - try it free, zero obligation"
        body = f"""Hi {hi_name},

No pitch, no pressure - just an offer:

2-week free trial of an AI phone system that:
- Answers 100% of your calls (even during {rush_phrase})
- Sounds like a real human (not robotic)
- Handles English, Mandarin, Malay
- Takes zero setup time

If you hate it, we part as friends. If it works, we can talk.

Currently testing with {biz_word}s across Singapore & Jakarta{chain_str}.

Worth trying?
{calendar}

{sig}

P.S. - Built by SMU & Columbia grads who understand the lunch-dinner double-rush grind.

Reply 'unsubscribe' to opt out."""

    return subject, body


def get_next_template(assignments: list) -> str:
    if not assignments:
        return "A"
    counts = {t: sum(1 for a in assignments if a.get("Template_Assigned") == t) for t in TEMPLATE_ORDER}
    return min(counts, key=counts.get)


def check_word_count(body: str) -> int:
    return len(body.split())


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(2, "email-writer", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 2 - Email Writer starting up", "INFO")

    if not loop_prevention_check(2, log_path):
        return
    update_last_run(2)

    config = load_config()
    do_not_contact = [x.lower() for x in config.get("do_not_contact", [])]
    log(log_path, "Config loaded", "SUCCESS")

    # Read today's leads
    today = datetime.now().strftime("%Y-%m-%d")
    leads_file = BASE_DIR / "data" / "leads" / f"{today}-new-leads.csv"
    if not leads_file.exists():
        log(log_path, f"No leads file found for {today}. Run Agent 1 first.", "ERROR")
        return

    leads = read_csv(leads_file)
    log(log_path, f"Loaded {len(leads)} leads from {leads_file.name}", "SUCCESS")

    # Load existing template assignments
    existing_assignments = read_csv(ASSIGNMENTS_FILE) if ASSIGNMENTS_FILE.exists() else []

    AUTO_SEND_DIR.mkdir(parents=True, exist_ok=True)
    APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

    created = []
    pending_count = 0
    autosend_count = 0
    new_assignments = []

    for i, lead in enumerate(leads):
        name = lead["Business_Name"]

        # Skip do-not-contact
        if name.lower() in do_not_contact:
            log(log_path, f"SKIPPING {name} (do-not-contact list)", "WARNING")
            continue

        # Assign template
        template = get_next_template(existing_assignments + new_assignments)
        subject, body = build_email(lead, template, config)
        word_count = check_word_count(body)
        score = int(lead.get("Lead_Score", 50))

        # Determine routing
        needs_approval = score >= 75
        dest_dir = APPROVAL_DIR if needs_approval else AUTO_SEND_DIR
        slug = name.lower().replace(" ", "-").replace("'", "").replace("&", "and")[:40]

        # Save JSON
        email_data = {
            "lead_name": name,
            "business_type": lead.get("Business_Type"),
            "lead_score": score,
            "template_used": template,
            "subject_line": subject,
            "email_body": body,
            "email_address": lead.get("Email_Address"),
            "personalization_elements": [
                f"Business name: {name}",
                f"Neighborhood: {lead.get('Neighborhood', 'Singapore')}",
                f"Chain: {'Yes (' + str(lead.get('Number_of_Locations','1')) + ' locations)' if lead.get('Is_Chain')=='Y' else 'Single location'}",
            ],
            "approval_required": needs_approval,
            "created_date": today,
            "send_status": "pending_approval" if needs_approval else "ready_to_send",
            "assigned_to_agent_3": False,
            "word_count": word_count,
        }
        json_path = dest_dir / f"{slug}.json"
        txt_path  = dest_dir / f"{slug}.txt"
        json_path.write_text(json.dumps(email_data, indent=2))
        txt_path.write_text(f"Subject: {subject}\n\n{body}")

        # Track
        new_assignments.append({
            "Lead_Name": name,
            "Business_Type": lead.get("Business_Type"),
            "Lead_Score": score,
            "Template_Assigned": template,
            "Date_Assigned": today,
        })
        created.append(email_data)
        if needs_approval:
            pending_count += 1
            log(log_path, f"[{i+1}/{len(leads)}] {name} → Template {template} → PENDING APPROVAL (score={score})", "WARNING")
        else:
            autosend_count += 1
            log(log_path, f"[{i+1}/{len(leads)}] {name} → Template {template} → auto-send (score={score}, {word_count}w)", "SUCCESS")

        if (i + 1) % 10 == 0:
            checkpoint(log_path, f"{i+1}/{len(leads)}", {
                "Auto-send": autosend_count,
                "Pending approval": pending_count,
                "Last template": template,
            })

    # Save assignment tracking
    append_csv(ASSIGNMENTS_FILE, new_assignments, ASSIGNMENTS_FIELDS)
    log(log_path, f"Template assignments saved to {ASSIGNMENTS_FILE.name}", "SUCCESS")

    # Summary
    dist = {t: sum(1 for a in new_assignments if a["Template_Assigned"] == t) for t in TEMPLATE_ORDER}
    summary_text = (
        f"Emails created: {len(created)}\n"
        f"Auto-send ready: {autosend_count}\n"
        f"Pending Sean approval: {pending_count}\n"
        f"Templates: A={dist['A']} B={dist['B']} C={dist['C']} D={dist['D']}"
    )
    write_summary(log_path, 2, start_time, "SUCCESS", {
        "Emails Created": len(created),
        "Auto-Send Ready": autosend_count,
        "Pending Approval": pending_count,
        f"Template Distribution": f"A={dist['A']} B={dist['B']} C={dist['C']} D={dist['D']}",
    })
    update_daily_summary(2, "Email Writer", summary_text)
    log(log_path, "Agent 2 complete ✓", "SUCCESS")
    return created


if __name__ == "__main__":
    run(test_mode=True)
