#!/bin/zsh
# Daily job-hunt runner — invoked by launchd at 10:00.
cd /Users/geraldofori/job-hunt || exit 1
./venv/bin/python scripts/daily.py "$@" >> logs/launchd.out 2>&1
