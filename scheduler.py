"""
SWOPLABS SCHEDULER
Runs all agents on their defined schedules using APScheduler.
Timezone: Asia/Singapore (UTC+8)

Usage:
    pip3 install apscheduler
    python3 scheduler.py

Runs as a background process. Keep this terminal open, or use:
    nohup python3 scheduler.py > logs/scheduler.log 2>&1 &
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/Users/Sean/Swoplabs")
sys.path.insert(0, str(BASE_DIR))

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "logs" / "scheduler.log"),
    ]
)
logger = logging.getLogger("swoplabs.scheduler")

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    print("❌ APScheduler not installed. Run: pip3 install apscheduler")
    sys.exit(1)

# ── Agent runners ──────────────────────────────────────────────────────────

def run_agent_1():
    logger.info("🔍 Agent 1 (Lead Scout) starting...")
    try:
        from agents.agent1 import run
        run(test_mode=False)
        logger.info("✅ Agent 1 complete")
    except Exception as e:
        logger.error(f"❌ Agent 1 failed: {e}", exc_info=True)

def run_agent_2():
    logger.info("✍️  Agent 2 (Email Writer) starting...")
    try:
        from agents.agent2 import run
        run(test_mode=False)
        logger.info("✅ Agent 2 complete")
    except Exception as e:
        logger.error(f"❌ Agent 2 failed: {e}", exc_info=True)

def run_agent_3():
    logger.info("📤 Agent 3 (Campaign Manager) starting...")
    try:
        from agents.agent3 import run
        run(test_mode=False)
        logger.info("✅ Agent 3 complete")
    except Exception as e:
        logger.error(f"❌ Agent 3 failed: {e}", exc_info=True)

def run_agent_4():
    logger.info("📊 Agent 4 (Analytics Tracker) starting...")
    try:
        from agents.agent4 import run
        run(test_mode=False)
        logger.info("✅ Agent 4 complete")
    except Exception as e:
        logger.error(f"❌ Agent 4 failed: {e}", exc_info=True)

def run_agent_5():
    logger.info("💡 Agent 5 (Insights Generator) starting...")
    try:
        from agents.agent5 import run
        run(test_mode=False)
        logger.info("✅ Agent 5 complete")
    except Exception as e:
        logger.error(f"❌ Agent 5 failed: {e}", exc_info=True)

def run_agent_6():
    logger.info("🔭 Agent 6 (Oversight Monitor) starting...")
    try:
        from agents.agent6 import run
        run(test_mode=False)
        logger.info("✅ Agent 6 complete")
    except Exception as e:
        logger.error(f"❌ Agent 6 failed: {e}", exc_info=True)

def run_agent_2_after_1():
    """Agent 2 runs 5 hours after Agent 1 (9AM + 5h = 2PM)"""
    run_agent_2()


# ── Scheduler setup ────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  🚀 SWOPLABS SCHEDULER STARTING")
    print("  Timezone: Asia/Singapore (SGT / UTC+8)")
    print("=" * 52)

    scheduler = BlockingScheduler(timezone="Asia/Singapore")

    # ── Agent 1: Lead Scout — Mon-Fri at 9:00 AM SGT ──────────────────────
    scheduler.add_job(
        run_agent_1,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone="Asia/Singapore"),
        id="agent_1_lead_scout",
        name="Agent 1 — Lead Scout",
        misfire_grace_time=3600,
    )

    # ── Agent 2: Email Writer — Mon-Fri at 2:00 PM SGT ────────────────────
    scheduler.add_job(
        run_agent_2,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=0, timezone="Asia/Singapore"),
        id="agent_2_email_writer",
        name="Agent 2 — Email Writer",
        misfire_grace_time=3600,
    )

    # ── Agent 3: Campaign Manager — Tue-Fri at 9:00 AM SGT ───────────────
    scheduler.add_job(
        run_agent_3,
        CronTrigger(day_of_week="tue-fri", hour=9, minute=15, timezone="Asia/Singapore"),
        id="agent_3_campaign_manager",
        name="Agent 3 — Campaign Manager",
        misfire_grace_time=3600,
    )

    # ── Agent 4: Analytics Tracker — Daily at 6:00 PM SGT ────────────────
    scheduler.add_job(
        run_agent_4,
        CronTrigger(hour=18, minute=0, timezone="Asia/Singapore"),
        id="agent_4_analytics",
        name="Agent 4 — Analytics Tracker",
        misfire_grace_time=3600,
    )

    # ── Agent 5: Insights Generator — Sunday at 10:00 AM SGT ─────────────
    scheduler.add_job(
        run_agent_5,
        CronTrigger(day_of_week="sun", hour=10, minute=0, timezone="Asia/Singapore"),
        id="agent_5_insights",
        name="Agent 5 — Insights Generator",
        misfire_grace_time=3600,
    )

    # ── Agent 6: Oversight Monitor — Every 6 hours ────────────────────────
    scheduler.add_job(
        run_agent_6,
        CronTrigger(hour="0,6,12,18", minute=30, timezone="Asia/Singapore"),
        id="agent_6_oversight",
        name="Agent 6 — Oversight Monitor",
        misfire_grace_time=1800,
    )

    # Print schedule
    print("\n📅 SCHEDULED JOBS:")
    print("-" * 52)
    for job in scheduler.get_jobs():
        print(f"  • {job.name}")
        print(f"    Next run: {job.next_run_time}")
    print("-" * 52)
    print("\n✅ Scheduler running. Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n\n🛑 Scheduler stopped by user.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
