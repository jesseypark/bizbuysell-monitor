#!/bin/bash
cd "$(dirname "$0")"
# Skip weekends (launchd doesn't filter by day-of-week)
[[ $(date +%u) -gt 5 ]] && exit 0
source venv/bin/activate
python3 monitor.py >> monitor.log 2>&1
