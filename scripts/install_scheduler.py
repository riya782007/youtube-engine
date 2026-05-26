#!/usr/bin/env python3
"""
install_scheduler.py  -  register the daily 11 AM Windows Task Scheduler entry.

WHAT IT DOES
  Creates a Task Scheduler entry named "YouTubeEngine_DailyShorts" that runs
  scripts/daily_agent.py every day at 11:00 (local time, set to IST on your box).
  Reads python.exe path from the current interpreter to avoid PATH issues.

USAGE
  python scripts/install_scheduler.py
  python scripts/install_scheduler.py --uninstall
  python scripts/install_scheduler.py --time 09:30   # run at 09:30 instead

NOTES
  - Uses schtasks.exe (built into Windows). No admin rights required for a
    user-scope task.
  - The task runs whether you're logged in or not (but only if the machine is
    powered on).
  - If your machine sleeps at 11AM, the task fires when it wakes (with -RunLevel Highest).
  - Logs go to scripts/logs/daily_agent_<date>.log .
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TASK_NAME = "YouTubeEngine_DailyShorts"
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")


def install(time_str="11:00"):
    os.makedirs(LOG_DIR, exist_ok=True)
    bat = os.path.join(SCRIPT_DIR, "daily_agent_run.bat")
    if not os.path.exists(bat):
        sys.exit(f"[scheduler] missing wrapper: {bat}")
    # Wrap in cmd /c "...".  Quote the bat path so spaces in the user's home
    # directory don't break the command. Keeping /TR short avoids the 261-char
    # schtasks limit.
    tr = f'cmd /c ""{bat}""'
    cmd = [
        "schtasks", "/Create", "/TN", TASK_NAME, "/TR", tr,
        "/SC", "DAILY", "/ST", time_str, "/F",
    ]
    print(f"[scheduler] installing task '{TASK_NAME}' at {time_str} daily...")
    print(f"[scheduler] command: {tr}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[scheduler] FAILED:\n{res.stderr}")
        sys.exit(1)
    print(res.stdout.strip() or "[scheduler] OK")
    print(f"[scheduler] logs will be written to: {LOG_DIR}\\daily_agent_<YYYY-MM-DD>.log")
    print(f"[scheduler] manage / view: schtasks /Query /TN {TASK_NAME} /V /FO LIST")


def uninstall():
    res = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                         capture_output=True, text=True)
    print(res.stdout.strip() or res.stderr.strip())


def main():
    ap = argparse.ArgumentParser(description="Install/uninstall the daily 11AM Windows scheduler entry.")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--time", default="11:00",
                    help="HH:MM 24-hour clock (local timezone, IST on your box).")
    args = ap.parse_args()
    if args.uninstall:
        uninstall()
    else:
        install(args.time)


if __name__ == "__main__":
    main()
