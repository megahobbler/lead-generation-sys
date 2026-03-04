"""
AGENT 6: OVERSIGHT MONITOR
Checks all 6 agents' health, disk space, config integrity.
Generates daily oversight report with 🟢/🟡/🔴 status.
"""
import sys
import shutil
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, write_summary,
    loop_prevention_check, update_last_run,
    read_csv, update_daily_summary
)

LOG_DIR       = BASE_DIR / "logs" / "execution-history"
OVERSIGHT_DIR = BASE_DIR / "oversight" / "daily-reports"
INCIDENT_DIR  = BASE_DIR / "oversight" / "incident-reports"
CAMPAIGN_LOG  = BASE_DIR / "data" / "tracking" / "campaign-log.csv"
CONFIG_DIR    = BASE_DIR / "config"

AGENT_NAMES = {
    1: ("Lead Scout",          "Mon-Fri 9:00 AM",   24),
    2: ("Email Writer",        "Daily after Agent 1", 24),
    3: ("Campaign Manager",    "Tue-Fri 9:00 AM",   24),
    4: ("Analytics Tracker",   "Daily 6:00 PM",     24),
    5: ("Insights Generator",  "Sunday 10:00 AM",   168),
    6: ("Oversight Monitor",   "Every 6 hours",     7),
}

CONFIG_FILES = [
    "calendar-link.txt", "contact-info.txt", "do-not-contact-list.txt",
    "approved-stats.txt", "vip-prospects.txt", "known-contacts.txt",
]


def check_agent(agent_num: int) -> dict:
    name, schedule, max_hours = AGENT_NAMES[agent_num]
    last_run_file = LOG_DIR / f"agent-{agent_num}" / ".last-run"

    if not last_run_file.exists():
        return {"name": name, "schedule": schedule, "status": "never_run",
                "indicator": "🟡", "last_run": "Never", "hours_ago": None,
                "detail": "Not yet executed"}

    try:
        last_run = datetime.fromisoformat(last_run_file.read_text().strip())
        hours_ago = (datetime.now() - last_run).total_seconds() / 3600

        if hours_ago <= max_hours:
            indicator = "🟢"
            status = "healthy"
        elif hours_ago <= max_hours * 2:
            indicator = "🟡"
            status = "stale"
        else:
            indicator = "🔴"
            status = "overdue"

        return {
            "name": name, "schedule": schedule, "status": status,
            "indicator": indicator,
            "last_run": last_run.strftime("%Y-%m-%d %I:%M %p"),
            "hours_ago": round(hours_ago, 1),
            "detail": f"{hours_ago:.1f}h ago",
        }
    except Exception as e:
        return {"name": name, "schedule": schedule, "status": "error",
                "indicator": "🔴", "last_run": "Error", "hours_ago": None,
                "detail": str(e)}


def check_campaign_health() -> dict:
    rows = read_csv(CAMPAIGN_LOG)
    if not rows:
        return {"status": "no_data", "indicator": "🟡", "detail": "No campaign data yet"}

    total     = len(rows)
    bounced   = sum(1 for r in rows if r.get("Delivered") == "N")
    spam      = 0  # Would check spam complaints in live mode
    bounce_rt = round(bounced / total * 100, 1) if total > 0 else 0

    if bounce_rt > 15:
        return {"status": "critical", "indicator": "🔴",
                "detail": f"Bounce rate {bounce_rt}% EXCEEDS 15% threshold!",
                "bounce_rate": bounce_rt, "total": total}
    if bounce_rt > 10:
        return {"status": "warning", "indicator": "🟡",
                "detail": f"Bounce rate {bounce_rt}% elevated (>10%)",
                "bounce_rate": bounce_rt, "total": total}
    return {"status": "healthy", "indicator": "🟢",
            "detail": f"Bounce rate {bounce_rt}% (healthy)", "bounce_rate": bounce_rt, "total": total}


def check_disk() -> dict:
    try:
        total, used, free = shutil.disk_usage(str(BASE_DIR))
        free_gb   = free / (1024 ** 3)
        free_pct  = free / total * 100
        if free_gb < 1:
            return {"indicator": "🔴", "detail": f"CRITICAL: Only {free_gb:.1f}GB free!"}
        if free_gb < 5:
            return {"indicator": "🟡", "detail": f"Low disk: {free_gb:.1f}GB free ({free_pct:.0f}%)"}
        return {"indicator": "🟢", "detail": f"{free_gb:.1f}GB free ({free_pct:.0f}%)"}
    except:
        return {"indicator": "🟡", "detail": "Could not check disk space"}


def check_configs() -> dict:
    missing = [f for f in CONFIG_FILES if not (CONFIG_DIR / f).exists()]
    if missing:
        return {"indicator": "🔴", "detail": f"Missing config files: {', '.join(missing)}"}
    return {"indicator": "🟢", "detail": "All config files intact"}


def create_incident(title: str, detail: str, severity: str = "WARNING"):
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = INCIDENT_DIR / f"incident-{ts}.txt"
    content = f"""INCIDENT REPORT
===============
Time: {datetime.now().isoformat()}
Severity: {severity}
Status: OPEN

ISSUE:
{title}

DETAILS:
{detail}

ACTION TAKEN:
- Oversight Monitor flagged this issue
- Sean should review and resolve

---
Created: {datetime.now().isoformat()}
"""
    path.write_text(content)
    return path


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(6, "oversight", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 6 - Oversight Monitor starting up", "INFO")

    if not loop_prevention_check(6, log_path, min_interval_minutes=3):
        return
    update_last_run(6)

    today = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M")
    incidents = []

    log(log_path, "Checking all agents...", "INFO")
    agent_results = {n: check_agent(n) for n in range(1, 7)}

    for n, result in agent_results.items():
        log(log_path, f"Agent {n} ({result['name']}): {result['indicator']} {result['status']} — {result['detail']}", "INFO")
        if result["indicator"] == "🔴":
            inc = create_incident(f"Agent {n} ({result['name']}) is {result['status']}", result["detail"], "CRITICAL")
            incidents.append(inc)
            log(log_path, f"🚨 INCIDENT CREATED for Agent {n}", "ERROR")

    campaign_health = check_campaign_health()
    log(log_path, f"Campaign health: {campaign_health['indicator']} {campaign_health['detail']}", "INFO")
    if campaign_health["indicator"] == "🔴":
        inc = create_incident("High bounce rate detected", campaign_health["detail"], "CRITICAL")
        incidents.append(inc)

    disk = check_disk()
    log(log_path, f"Disk space: {disk['indicator']} {disk['detail']}", "INFO")
    if disk["indicator"] == "🔴":
        inc = create_incident("Low disk space", disk["detail"], "CRITICAL")
        incidents.append(inc)

    configs = check_configs()
    log(log_path, f"Config files: {configs['indicator']} {configs['detail']}", "INFO")

    # Overall status
    all_indicators = [r["indicator"] for r in agent_results.values()] + [campaign_health["indicator"], disk["indicator"], configs["indicator"]]
    if any(i == "🔴" for i in all_indicators):
        overall = "🔴 CRITICAL ISSUES DETECTED"
    elif any(i == "🟡" for i in all_indicators):
        overall = "🟡 MINOR ISSUES"
    else:
        overall = "🟢 ALL SYSTEMS OPERATIONAL"

    log(log_path, f"OVERALL: {overall}", "SUCCESS" if "🟢" in overall else "WARNING")

    # ── Generate daily report ──────────────────────────────────────────────
    OVERSIGHT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OVERSIGHT_DIR / f"oversight-{today}.md"

    rows = read_csv(CAMPAIGN_LOG)
    total_sent = len(rows)
    today_rows = [r for r in rows if r.get("Sent_Date") == today]
    positive   = sum(1 for r in rows if r.get("Reply_Type") == "Positive")
    meetings   = sum(1 for r in rows if r.get("Meeting_Booked") == "Y")

    pending_approval = list((BASE_DIR / "data" / "emails" / "pending-approval").glob("*.json"))
    auto_send_queue  = list((BASE_DIR / "data" / "emails" / "auto-send").glob("*.json"))
    today_leads_files = list((BASE_DIR / "data" / "leads").glob(f"{today}-*.csv"))
    leads_today = sum(1 for r in read_csv(today_leads_files[0])) if today_leads_files else 0

    report = f"""# SWOPLABS OVERSIGHT REPORT
Date: {today}
Report Time: {time_str}

---

## SYSTEM STATUS: {overall}

---

## AGENT HEALTH

"""
    for n, r in agent_results.items():
        report += f"""### Agent {n} — {r['name']}
- Status: {r['indicator']} {r['status'].replace('_', ' ').title()}
- Schedule: {r['schedule']}
- Last Run: {r['last_run']}
- Detail: {r['detail']}

"""

    report += f"""---

## CAMPAIGN HEALTH
- Bounce Rate: {campaign_health['indicator']} {campaign_health['detail']}
- Disk Space: {disk['indicator']} {disk['detail']}
- Config Files: {configs['indicator']} {configs['detail']}

---

## DATA SUMMARY

| Metric | Value |
|---|---|
| Leads found today | {leads_today} |
| Emails sent today | {len(today_rows)} |
| Total emails sent | {total_sent} |
| Pending approval | {len(pending_approval)} |
| Auto-send queue | {len(auto_send_queue)} |
| Positive replies | {positive} |
| Meetings booked | {meetings} |

---

## INCIDENTS ({len(incidents)} open)
"""
    if incidents:
        for inc in incidents:
            report += f"- 🚨 {inc.name}\n"
    else:
        report += "- ✓ No active incidents\n"

    report += f"""
---

## ACTION ITEMS FOR SEAN

"""
    if pending_approval:
        report += f"- **IMMEDIATE:** Review {len(pending_approval)} high-value emails in pending-approval/\n"
    if positive > 0:
        report += f"- **FOLLOW UP:** {positive} positive reply(ies) waiting for your response\n"
    if not pending_approval and positive == 0:
        report += "- No immediate actions required\n"

    report += f"""
---

*Next oversight check: in 6 hours*
*Generated: {datetime.now().isoformat()}*
"""
    report_path.write_text(report)
    log(log_path, f"Oversight report saved → {report_path.name}", "SUCCESS")

    summary_text = (
        f"Overall: {overall}\n"
        f"Incidents: {len(incidents)}\n"
        f"Pending approvals: {len(pending_approval)}\n"
        f"Positive replies: {positive}"
    )
    write_summary(log_path, 6, start_time, "SUCCESS", {
        "Overall Status": overall,
        "Incidents": len(incidents),
        "Pending Approvals": len(pending_approval),
    })
    update_daily_summary(6, "Oversight Monitor", summary_text)
    log(log_path, "Agent 6 complete ✓", "SUCCESS")
    return overall


if __name__ == "__main__":
    run(test_mode=True)
