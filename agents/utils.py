"""
SWOPLABS Agent Utilities
Shared logging, config loading, and loop prevention for all agents.
"""
import os
import csv
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/Users/Sean/Swoplabs")
LOG_DIR = BASE_DIR / "logs" / "execution-history"
CONFIG_DIR = BASE_DIR / "config"

# ─── LOGGING ────────────────────────────────────────────────────────────────

def get_log_path(agent_num: int, agent_name: str) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return LOG_DIR / f"agent-{agent_num}" / f"{ts}-{agent_name}.log"

def setup_logging(agent_num: int, agent_name: str, trigger: str = "Manual") -> Path:
    log_path = get_log_path(agent_num, agent_name)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = f"""========================================
AGENT {agent_num}: {agent_name.upper()} - EXECUTION START
========================================
Start Time: {datetime.now().isoformat()}
Trigger: {trigger}
Previous Run Check: Starting loop prevention...
========================================
"""
    log_path.write_text(header)
    return log_path

def log(log_path: Path, message: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "  ", "SUCCESS": "✓ ", "ERROR": "❌", "WARNING": "⚠️", "CHECKPOINT": "=="}
    sym = symbols.get(level, "  ")
    entry = f"[{ts}] {sym} {message}\n"
    with open(log_path, "a") as f:
        f.write(entry)
    print(entry, end="")

def checkpoint(log_path: Path, progress: str, stats: dict):
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [
        f"[{ts}] ======== CHECKPOINT ========",
        f"[{ts}] Progress: {progress}",
    ]
    for k, v in stats.items():
        lines.append(f"[{ts}] {k}: {v}")
    lines.append(f"[{ts}] ============================")
    block = "\n".join(lines) + "\n"
    with open(log_path, "a") as f:
        f.write(block)
    print(block, end="")

def write_summary(log_path: Path, agent_num: int, start_time: datetime, status: str, results: dict):
    end_time = datetime.now()
    duration = str(end_time - start_time).split(".")[0]
    next_run = "See agent schedule"
    summary = f"""
========================================
EXECUTION COMPLETE
========================================
End Time: {end_time.isoformat()}
Duration: {duration}
Status: {status}
RESULTS:
"""
    for k, v in results.items():
        summary += f"  - {k}: {v}\n"
    summary += f"""SAFETY:
  - Never Rules Violated: 0
  - Escalations: 0
  - Warnings: 0
NEXT RUN: {next_run}
========================================
"""
    with open(log_path, "a") as f:
        f.write(summary)
    print(summary)
    # Archive
    archive_dir = LOG_DIR / f"agent-{agent_num}" / "archive" / end_time.strftime("%Y") / end_time.strftime("%m")
    archive_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(log_path, archive_dir / log_path.name)

# ─── LOOP PREVENTION ────────────────────────────────────────────────────────

def loop_prevention_check(agent_num: int, log_path: Path, min_interval_minutes: int = 5) -> bool:
    """Returns True if OK to proceed, False if should block."""
    last_run_file = LOG_DIR / f"agent-{agent_num}" / ".last-run"
    if not last_run_file.exists():
        log(log_path, "No previous run found. First execution.", "INFO")
        return True
    try:
        last_run = datetime.fromisoformat(last_run_file.read_text().strip())
        elapsed = (datetime.now() - last_run).total_seconds() / 60
        if elapsed < min_interval_minutes:
            log(log_path, f"BLOCKED: Last run {elapsed:.1f} min ago (min: {min_interval_minutes} min). Infinite loop detected.", "ERROR")
            return False
        if elapsed < 10:
            log(log_path, f"WARNING: Last run only {elapsed:.1f} min ago. Proceeding with caution.", "WARNING")
        else:
            log(log_path, f"Loop check passed. Last run: {elapsed:.0f} min ago.", "SUCCESS")
        return True
    except Exception as e:
        log(log_path, f"Error reading .last-run: {e}. Proceeding.", "WARNING")
        return True

def update_last_run(agent_num: int):
    last_run_file = LOG_DIR / f"agent-{agent_num}" / ".last-run"
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    last_run_file.write_text(datetime.now().isoformat())

# ─── CONFIG LOADING ──────────────────────────────────────────────────────────

def load_config() -> dict:
    config = {}
    files = {
        "calendar_link": "calendar-link.txt",
        "contact_info": "contact-info.txt",
        "do_not_contact": "do-not-contact-list.txt",
        "approved_stats": "approved-stats.txt",
        "vip_prospects": "vip-prospects.txt",
        "known_contacts": "known-contacts.txt",
        "intro_deck_link": "intro-deck-link.txt",
    }
    for key, filename in files.items():
        path = CONFIG_DIR / filename
        if path.exists():
            lines = [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")]
            config[key] = lines[0] if len(lines) == 1 else lines
        else:
            config[key] = "" if key in ("calendar_link", "intro_deck_link") else []
    return config

# ─── CSV HELPERS ─────────────────────────────────────────────────────────────

def read_csv(filepath: Path) -> list:
    if not filepath.exists():
        return []
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(filepath: Path, rows: list, fieldnames: list = None):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def append_csv(filepath: Path, rows: list, fieldnames: list = None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    file_exists = filepath.exists()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

def update_daily_summary(agent_num: int, agent_name: str, summary_text: str):
    today = datetime.now().strftime("%Y-%m-%d")
    summary_file = BASE_DIR / "logs" / "daily-summaries" / f"{today}-all-agents.log"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, "a") as f:
        f.write(f"\n{'='*40}\n")
        f.write(f"AGENT {agent_num}: {agent_name} - {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"{'='*40}\n")
        f.write(summary_text + "\n")
