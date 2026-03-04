"""
SWOPLABS TEST WORKFLOW
Runs all 6 agents in sequence with test data.
Populates the dashboard with realistic sample data.

Usage:
    python3 test_workflow.py
"""
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/Users/Sean/Swoplabs")
sys.path.insert(0, str(BASE_DIR))

def separator(title=""):
    width = 52
    print("\n" + "=" * width)
    if title:
        pad = (width - len(title) - 2) // 2
        print(" " * pad + f" {title} ")
        print("=" * width)

def run_agent(num, name, func, test_mode=True):
    separator(f"AGENT {num}: {name.upper()}")
    print(f"⏱  Starting at {datetime.now().strftime('%H:%M:%S')}...")
    try:
        result = func(test_mode=test_mode)
        print(f"✅ Agent {num} complete")
        return result
    except Exception as e:
        print(f"❌ Agent {num} FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    separator("SWOPLABS WORKFLOW TEST")
    print(f"Starting full pipeline test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base directory: {BASE_DIR}")
    print(f"\nThis will run all 6 agents and populate the dashboard with")
    print(f"realistic test data. The server must be running separately.")

    # Import agents
    from agents.agent1 import run as run1
    from agents.agent2 import run as run2
    from agents.agent3 import run as run3
    from agents.agent4 import run as run4
    from agents.agent5 import run as run5
    from agents.agent6 import run as run6

    start = datetime.now()

    # Run pipeline
    leads   = run_agent(1, "Lead Scout",        run1)
    time.sleep(1)
    emails  = run_agent(2, "Email Writer",       run2)
    time.sleep(1)
    sent    = run_agent(3, "Campaign Manager",   run3)
    time.sleep(1)
    metrics = run_agent(4, "Analytics Tracker",  run4)
    time.sleep(1)
    insight = run_agent(5, "Insights Generator", run5)
    time.sleep(1)
    health  = run_agent(6, "Oversight Monitor",  run6)

    # Final summary
    separator("WORKFLOW COMPLETE")
    duration = str(datetime.now() - start).split(".")[0]

    from agents.utils import read_csv, BASE_DIR as BD
    from pathlib import Path
    import json

    campaign_rows = read_csv(BD / "data" / "tracking" / "campaign-log.csv")
    pending = list((BD / "data" / "emails" / "pending-approval").glob("*.json"))
    today_str = datetime.now().strftime("%Y-%m-%d")
    lead_file = BD / "data" / "leads" / f"{today_str}-new-leads.csv"
    lead_rows = read_csv(lead_file) if lead_file.exists() else []

    opens    = sum(1 for r in campaign_rows if r.get("Opened") == "Y")
    replies  = sum(1 for r in campaign_rows if r.get("Reply_Received") == "Y")
    positive = sum(1 for r in campaign_rows if r.get("Reply_Type") == "Positive")
    meetings = sum(1 for r in campaign_rows if r.get("Meeting_Booked") == "Y")
    open_rate  = round(opens / len(campaign_rows) * 100, 1) if campaign_rows else 0
    reply_rate = round(replies / len(campaign_rows) * 100, 1) if campaign_rows else 0

    print(f"""
┌─────────────────────────────────────────────┐
│         SWOPLABS TEST RESULTS               │
├─────────────────────────────────────────────┤
│  ⏱  Duration:          {duration:<21}│
│  👥  Leads found:       {len(lead_rows):<21}│
│  📧  Emails sent:       {len(campaign_rows):<21}│
│  📬  Open rate:         {str(open_rate)+'%':<21}│
│  💬  Reply rate:        {str(reply_rate)+'%':<21}│
│  🎉  Positive replies:  {positive:<21}│
│  📅  Meetings booked:   {meetings:<21}│
│  ⏳  Pending approval:  {len(pending):<21}│
│  🩺  System health:     {str(health or 'See report')[:21]:<21}│
└─────────────────────────────────────────────┘

✅ Dashboard should now show live data at:
   http://localhost:8080

📋 Key files created:
   • data/leads/{today_str}-new-leads.csv
   • data/tracking/campaign-log.csv
   • analytics/daily-performance-{today_str}.csv
   • analytics/ab-test-results/weekly-{today_str}.csv
   • analytics/weekly-insights/insights-{today_str}.md
   • oversight/daily-reports/oversight-{today_str}.md
""")

    if pending:
        print(f"⚠️  {len(pending)} high-value email(s) need your approval:")
        for p in pending[:5]:
            try:
                data = json.loads(p.read_text())
                print(f"   • {data['lead_name']} (score: {data['lead_score']}, template: {data['template_used']})")
            except:
                print(f"   • {p.stem}")
        print(f"\n   → Click 'View Pending Approvals' on the dashboard")

    if positive:
        print(f"\n🎉 {positive} positive reply(ies)!")
        pos_rows = [r for r in campaign_rows if r.get("Reply_Type") == "Positive"]
        for r in pos_rows[:5]:
            print(f"   • {r['Lead_Name']} ({r['Business_Type']}) — Meeting: {r.get('Meeting_Booked','N')}")

    print("\n" + "=" * 52)


if __name__ == "__main__":
    main()
