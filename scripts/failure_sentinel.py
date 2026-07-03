"""
Failure-streak sentinel for the Find Deals workflow.

The June 2026 fast-flights breakage turned the daily cron red for 3 weeks
before anyone noticed. This script makes silent death impossible:

  - called with no args after a FAILED run: bumps failure_streak.json and
    emails NOTIFY_EMAIL at 3 consecutive failures (then every 7th after).
  - called with --reset after a SUCCESSFUL run: zeroes the streak.

Deliberately stdlib-only — it must still work when `pip install` is the
thing that broke.
"""

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

STREAK_FILE = Path(__file__).parent.parent / "failure_streak.json"
ALERT_AT = 3  # email on the 3rd straight failure, then every 7th after

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)

ACTIONS_URL = "https://github.com/kanwia-ai/detty-flight-deals/actions"


def load_streak() -> int:
    if not STREAK_FILE.exists():
        return 0
    try:
        with open(STREAK_FILE, "r") as f:
            return int(json.load(f).get("consecutive_failures", 0))
    except (json.JSONDecodeError, IOError, ValueError):
        return 0


def save_streak(streak: int):
    with open(STREAK_FILE, "w") as f:
        json.dump({"consecutive_failures": streak}, f, indent=2)


def send_alert(streak: int) -> bool:
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("No SMTP credentials — cannot send failure alert")
        return False

    msg = MIMEText(
        f"The Find Deals workflow has failed {streak} days in a row.\n\n"
        f"Logs: {ACTIONS_URL}\n\n"
        f"Most likely culprit (it happened before, June 2026): a dependency "
        f"broke. Check the pin comment in requirements.txt.\n\n"
        f"Until this is fixed, nobody is getting deal alerts."
    )
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = f"🚨 Detty deal finder DOWN — {streak} straight failures"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"Failure alert sent to {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        print(f"Failed to send alert: {e}")
        return False


def main():
    if "--reset" in sys.argv:
        if load_streak() != 0:
            save_streak(0)
            print("Failure streak reset to 0")
        else:
            print("Failure streak already 0")
        return

    streak = load_streak() + 1
    save_streak(streak)
    print(f"Consecutive failures: {streak}")

    if streak == ALERT_AT or (streak > ALERT_AT and (streak - ALERT_AT) % 7 == 0):
        send_alert(streak)


if __name__ == "__main__":
    main()
