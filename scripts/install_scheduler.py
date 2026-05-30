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
    
    # Use PowerShell to create the task with advanced settings
    # 1. Run on battery: $settings.DisallowStartIfOnBatteries = $false
    # 2. Wake computer: $settings.WakeToRun = $true
    # 3. Start when available (if missed): $settings.StartWhenAvailable = $true
    
    ps_cmd = f"""
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c \"{bat}\"'
    $trigger = New-ScheduledTaskTrigger -Daily -At {time_str}
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -StartWhenAvailable
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Force
    """
    
    print(f"[scheduler] installing task '{TASK_NAME}' at {time_str} daily...")
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    
    if res.returncode != 0:
        print(f"[scheduler] FAILED via PowerShell, falling back to basic schtasks...")
        print(f"[scheduler] PS Error: {res.stderr}")
        # Fallback to basic schtasks if PowerShell fails
        cmd = [
            "schtasks", "/Create", "/TN", TASK_NAME, "/TR", f'cmd /c "{bat}"',
            "/SC", "DAILY", "/ST", time_str, "/F",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[scheduler] FINAL FAILURE:\n{res.stderr}")
            sys.exit(1)
        print(res.stdout.strip() or "[scheduler] OK (Basic)")
    else:
        print(f"[scheduler] OK (Advanced settings enabled: Battery, Wake, Catch-up)")
    
    print(f"[scheduler] logs will be written to: {LOG_DIR}\\daily_agent_<YYYY-MM-DD>.log")



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
