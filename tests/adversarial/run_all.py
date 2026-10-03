#!/usr/bin/env python3
"""Run all adversarial suites. Exit non-zero on failure.

Usage (from repo root):
  python3 tests/adversarial/run_all.py
  node --test tests/adversarial/test_presenter_adversarial.cjs
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADV = Path(__file__).resolve().parent


def run(cmd, cwd=ROOT):
    print('+', ' '.join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode


def main() -> int:
    failures = 0
    failures += run([sys.executable, '-m', 'unittest',
                     'tests.adversarial.test_access_control_contracts',
                     'tests.adversarial.test_backend_adversarial',
                     '-v'])
    # Ensure package path: run via file paths if package import fails
    if failures:
        # Retry as file-based discovery (no package install required)
        print('retrying via file paths...', flush=True)
        failures = run([sys.executable, '-m', 'unittest', 'discover',
                        '-s', str(ADV), '-p', 'test_*.py', '-v'])
    node = run(['node', '--test', str(ADV / 'test_presenter_adversarial.cjs')])
    failures = failures or node
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    # Prefer discover to avoid package init requirements
    code = run([sys.executable, '-m', 'unittest', 'discover',
                '-s', str(ADV), '-p', 'test_*.py', '-v'])
    node = run(['node', '--test', str(ADV / 'test_presenter_adversarial.cjs')])
    sys.exit(0 if code == 0 and node == 0 else 1)
