"""
Simple runner to keep the innovator pipeline running 24/7.

Usage:
  python keep_alive.py                    # Run pipeline in a loop every 6 hours
  python keep_alive.py --interval 3       # Every 3 hours instead
  python keep_alive.py --once             # Run once and exit

Schedule with Task Scheduler on Windows:
  schtasks /create /tn "GitHubInnovator" /tr "python C:\\path\\to\\keep_alive.py" /sc daily /st 06:00 /f

Or just leave this script running in a terminal.
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.graph import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="GitHub Innovation Fork Agent — 24/7 Runner")
    parser.add_argument("--interval", type=int, default=6, help="Hours between runs (default: 6)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        result = run_pipeline()
        print(f"[{result['status']}] Run #{result['run_id']}: {result.get('fork_url', 'no fork')}")
        return

    print(f"GitHub Innovation Fork Agent — running every {args.interval} hours")
    print("Press Ctrl+C to stop\n")

    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting pipeline...")
        try:
            result = run_pipeline()
            status = result["status"]
            fork = result.get("fork_url", "no fork")
            print(f"[{status}] Run #{result['run_id']} — {fork}")
        except Exception as e:
            print(f"[ERROR] {e}")

        print(f"Next run in {args.interval} hours...\n")
        time.sleep(args.interval * 3600)


if __name__ == "__main__":
    main()
