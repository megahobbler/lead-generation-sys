from flask import Flask, render_template, jsonify, send_file
import os
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

app = Flask(__name__)
BASE_DIR = Path("/Users/Sean/Swoplabs")

# Helper functions
def read_csv(filepath):
    """Read CSV file and return as list of dicts"""
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def get_latest_file(directory, pattern="*.csv"):
    """Get the most recent file in a directory"""
    files = list(Path(directory).glob(pattern))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def read_log_file(filepath, lines=50):
    """Read last N lines from a log file"""
    if not os.path.exists(filepath):
        return []

    with open(filepath, 'r') as f:
        all_lines = f.readlines()
        return all_lines[-lines:]

def get_agent_status(agent_number):
    """Check if agent ran recently and get status"""
    log_dir = BASE_DIR / "logs" / "execution-history" / f"agent-{agent_number}"
    last_run_file = log_dir / ".last-run"

    if not last_run_file.exists():
        return {
            "status": "never_run",
            "indicator": "yellow",
            "last_run": "Never",
            "output": "Not yet executed"
        }

    with open(last_run_file, 'r') as f:
        last_run_str = f.read().strip()

    try:
        last_run = datetime.fromisoformat(last_run_str)
        time_since = datetime.now() - last_run

        # Determine status
        if time_since < timedelta(hours=24):
            status = "healthy"
            indicator = "green"
        elif time_since < timedelta(hours=48):
            status = "warning"
            indicator = "yellow"
        else:
            status = "stale"
            indicator = "red"

        return {
            "status": status,
            "indicator": indicator,
            "last_run": last_run.strftime("%Y-%m-%d %I:%M %p"),
            "time_since": str(time_since).split('.')[0]
        }
    except:
        return {
            "status": "error",
            "indicator": "red",
            "last_run": "Error reading timestamp",
            "output": "Check logs"
        }

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/metrics')
def get_metrics():
    """Get current metrics"""

    # Read campaign log
    campaign_log = read_csv(BASE_DIR / "data" / "tracking" / "campaign-log.csv")

    # Calculate metrics
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    emails_sent_today = len([e for e in campaign_log if e.get('Sent_Date') == today_str])

    # Get total metrics
    total_sent = len(campaign_log)
    total_opened = len([e for e in campaign_log if e.get('Opened') == 'Y'])
    total_clicked = len([e for e in campaign_log if e.get('Link_Clicked') == 'Y'])
    total_replies = len([e for e in campaign_log if e.get('Reply_Received') == 'Y'])
    positive_replies = len([e for e in campaign_log if e.get('Reply_Type') == 'Positive'])
    meetings_booked = len([e for e in campaign_log if e.get('Meeting_Booked') == 'Y'])

    # Calculate rates
    open_rate = round((total_opened / total_sent * 100), 1) if total_sent > 0 else 0
    click_rate = round((total_clicked / total_sent * 100), 1) if total_sent > 0 else 0
    reply_rate = round((total_replies / total_sent * 100), 1) if total_sent > 0 else 0

    # Get leads today
    today_leads_file = get_latest_file(BASE_DIR / "data" / "leads", f"{today_str}-*.csv")
    leads_today = 0
    if today_leads_file:
        leads = read_csv(today_leads_file)
        leads_today = len(leads)

    return jsonify({
        "emails_sent_today": emails_sent_today,
        "daily_quota": 20,
        "leads_today": leads_today,
        "open_rate": open_rate,
        "reply_rate": reply_rate,
        "meetings_booked_week": meetings_booked,
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replies": total_replies,
        "positive_replies": positive_replies
    })

@app.route('/api/agents')
def get_agents():
    """Get status of all 6 agents"""

    agents = [
        {
            "number": 1,
            "name": "Lead Scout",
            "description": "Finds qualified restaurants/clinics",
            **get_agent_status(1)
        },
        {
            "number": 2,
            "name": "Email Writer",
            "description": "Creates personalized emails (A/B testing)",
            **get_agent_status(2)
        },
        {
            "number": 3,
            "name": "Campaign Manager",
            "description": "Sends emails, tracks engagement",
            **get_agent_status(3)
        },
        {
            "number": 4,
            "name": "Analytics Tracker",
            "description": "Measures performance, A/B test results",
            **get_agent_status(4)
        },
        {
            "number": 5,
            "name": "Insights Generator",
            "description": "Weekly recommendations",
            **get_agent_status(5)
        },
        {
            "number": 6,
            "name": "Oversight Monitor",
            "description": "Monitors all agents 24/7",
            **get_agent_status(6)
        }
    ]

    # Determine overall system status
    statuses = [a['indicator'] for a in agents]
    if all(s == 'green' for s in statuses):
        overall = "green"
    elif any(s == 'red' for s in statuses):
        overall = "red"
    else:
        overall = "yellow"

    return jsonify({
        "agents": agents,
        "overall_status": overall
    })

@app.route('/api/abtest')
def get_abtest():
    """Get A/B test results"""

    campaign_log = read_csv(BASE_DIR / "data" / "tracking" / "campaign-log.csv")

    templates = ['A', 'B', 'C', 'D']
    results = []

    for template in templates:
        template_emails = [e for e in campaign_log if e.get('Template_Used') == template]

        if not template_emails:
            results.append({
                "template": template,
                "name": get_template_name(template),
                "sent": 0,
                "open_rate": 0,
                "click_rate": 0,
                "reply_rate": 0,
                "confidence": "No Data"
            })
            continue

        sent = len(template_emails)
        opened = len([e for e in template_emails if e.get('Opened') == 'Y'])
        clicked = len([e for e in template_emails if e.get('Link_Clicked') == 'Y'])
        replied = len([e for e in template_emails if e.get('Reply_Received') == 'Y'])

        results.append({
            "template": template,
            "name": get_template_name(template),
            "sent": sent,
            "open_rate": round((opened / sent * 100), 1) if sent > 0 else 0,
            "click_rate": round((clicked / sent * 100), 1) if sent > 0 else 0,
            "reply_rate": round((replied / sent * 100), 1) if sent > 0 else 0,
            "confidence": "High" if sent >= 100 else "Medium" if sent >= 50 else "Low"
        })

    return jsonify(results)

def get_template_name(letter):
    names = {
        'A': 'Problem-Focused',
        'B': 'Proof-Focused',
        'C': 'Voice Quality',
        'D': 'Risk-Free'
    }
    return names.get(letter, 'Unknown')

@app.route('/api/logs/<int:agent_number>')
def get_logs(agent_number):
    """Get recent logs for an agent"""

    log_dir = BASE_DIR / "logs" / "execution-history" / f"agent-{agent_number}"
    latest_log = get_latest_file(log_dir, "*.log")

    if not latest_log:
        return jsonify({"logs": ["No logs found for this agent"]})

    lines = read_log_file(latest_log, lines=100)

    return jsonify({"logs": lines})

@app.route('/api/pending-approvals')
def get_pending_approvals():
    """Get high-value leads pending approval"""

    approval_dir = BASE_DIR / "data" / "emails" / "pending-approval"

    if not approval_dir.exists():
        return jsonify([])

    pending = []
    for email_file in approval_dir.glob("*.json"):
        try:
            with open(email_file, 'r') as f:
                data = json.load(f)
                pending.append({
                    "lead_name": data.get('lead_name'),
                    "lead_score": data.get('lead_score'),
                    "template": data.get('template_used'),
                    "subject": data.get('subject_line'),
                    "filename": email_file.name
                })
        except:
            continue

    return jsonify(pending)

@app.route('/api/alerts')
def get_alerts():
    """Get any system alerts"""

    incident_dir = BASE_DIR / "oversight" / "incident-reports"

    if not incident_dir.exists():
        return jsonify([])

    # Get incidents from last 7 days
    cutoff = datetime.now() - timedelta(days=7)
    alerts = []

    for incident_file in incident_dir.glob("*.txt"):
        file_time = datetime.fromtimestamp(os.path.getctime(incident_file))
        if file_time > cutoff:
            with open(incident_file, 'r') as f:
                content = f.read()
                alerts.append({
                    "time": file_time.strftime("%Y-%m-%d %I:%M %p"),
                    "content": content,
                    "severity": "CRITICAL" if "CRITICAL" in content else "WARNING"
                })

    return jsonify(alerts)

@app.route('/download/report/<report_type>')
def download_report(report_type):
    """Download various reports"""

    if report_type == "daily":
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = BASE_DIR / "analytics" / f"daily-performance-{today}.csv"
    elif report_type == "weekly":
        file_path = get_latest_file(BASE_DIR / "analytics" / "weekly-insights", "*.md")
    elif report_type == "abtest":
        file_path = get_latest_file(BASE_DIR / "analytics" / "ab-test-results", "*.csv")
    else:
        return "Report not found", 404

    if file_path and file_path.exists():
        return send_file(file_path, as_attachment=True)
    else:
        return "Report not found", 404

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 SWOPLABS DASHBOARD SERVER STARTING")
    print("="*50)
    print("\n📊 Dashboard will open at: http://localhost:8080")
    print("\n✅ Server running... Press CTRL+C to stop\n")

    app.run(debug=True, host='0.0.0.0', port=8080)
