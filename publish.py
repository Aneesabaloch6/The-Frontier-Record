#!/usr/bin/env python3
"""
publish.py — publish in one command.

    python publish.py                  build (with Urdu) + commit + push
    python publish.py "your message"   same, with your own commit message

After the push, Cloudflare rebuilds the LIVE site automatically (~1-2 minutes).
You never run a build command for the live site yourself.
"""

import datetime
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd):
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


def is_git_repo() -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else f"Update {datetime.date.today().isoformat()}"

    if not is_git_repo():
        print("This folder isn't connected to GitHub yet.")
        print("Set it up once with: git init, git remote add origin <your-repo-url>, "
              "then push. After that, publish.py will work.")
        sys.exit(1)

    # 1) Build locally with translation ON so Urdu files are created/updated.
    print("\n[1/3] Building (English + Urdu)...")
    if run([sys.executable, "scripts/build_from_markdown.py"]) != 0:
        print("\nBuild failed. Fix the error shown above, then run publish.py again.")
        sys.exit(1)

    # 2) Stage + commit (a 'nothing to commit' result is fine).
    print("\n[2/3] Saving changes...")
    run(["git", "add", "-A"])
    committed = run(["git", "commit", "-m", msg]) == 0
    if not committed:
        print("(No new changes to commit — continuing.)")

    # 3) Push -> Cloudflare auto-deploys.
    print("\n[3/3] Pushing to GitHub...")
    if run(["git", "push"]) != 0:
        print("\nPush failed. Check your internet connection or GitHub sign-in, then retry.")
        sys.exit(1)

    print("\nDone. Cloudflare will rebuild the live site in about a minute or two.")


if __name__ == "__main__":
    main()
