"""Schedule une sauvegarde automatique via cron (Linux/Mac) ou Task Scheduler (Windows).

Usage:
    python scripts/schedule_backup.py --interval daily    # Tous les jours a 02:00
    python scripts/schedule_backup.py --interval hourly   # Toutes les heures
    python scripts/schedule_backup.py remove              # Supprime la tache planifiee
"""
import argparse
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BACKUP_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "backup.sh"))
BACKUP_PS1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "backup.ps1"))
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")


def _ensure_backup_dir():
    """ ensure backup dir."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _schedule_linux(interval: str, remove: bool = False):
    """ schedule linux."""
    if remove:
        subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return
    cron_cmd = f"0 2 * * * cd {PROJECT_DIR} && bash {BACKUP_SCRIPT}"
    if interval == "hourly":
        cron_cmd = f"0 * * * * cd {PROJECT_DIR} && bash {BACKUP_SCRIPT}"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout
    if cron_cmd in existing:
        print("Deja planifie.")
        return
    new_cron = existing.strip() + "\n" + cron_cmd + "\n"
    proc = subprocess.Popen(["crontab"], stdin=subprocess.PIPE)
    proc.communicate(input=new_cron.encode())
    print(f"Planifie (linux): {cron_cmd}")


def _schedule_windows(interval: str, remove: bool = False):
    """ schedule windows."""
    task_name = "JARVIS Backup"
    if remove:
        subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)
        print(f"Tache '{task_name}' supprimee.")
        return
    freq = "DAILY"
    if interval == "hourly":
        freq = "HOURLY"
    cmd = [
        "schtasks", "/Create", "/SC", freq, "/TN", task_name,
        "/TR", f'powershell -File "{BACKUP_PS1}"',
        "/ST", "02:00", "/F",
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"Tache '{task_name}' creee (/{freq}).")


def main():
    """Main."""
    parser = argparse.ArgumentParser(description="Planifie une sauvegarde automatique")
    parser.add_argument("--interval", choices=["daily", "hourly"], default="daily")
    parser.add_argument("action", nargs="?", choices=["schedule", "remove"], default="schedule")
    args = parser.parse_args()

    _ensure_backup_dir()

    system = platform.system().lower()
    if system == "windows":
        _schedule_windows(args.interval, remove=(args.action == "remove"))
    else:
        _schedule_linux(args.interval, remove=(args.action == "remove"))


if __name__ == "__main__":
    main()
