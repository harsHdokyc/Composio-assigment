"""Run the full pipeline: research → analyze → verify → build page."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str]):
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=ROOT)


def main():
    run([sys.executable, "agent/research_agent.py"])
    run([sys.executable, "agent/analyze.py"])
    run([sys.executable, "agent/verify.py"])
    run([sys.executable, "scripts/build_page.py"])
    print("\nAll done. Open output/case-study.html in a browser.")


if __name__ == "__main__":
    main()
