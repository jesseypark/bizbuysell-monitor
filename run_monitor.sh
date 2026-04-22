#!/bin/bash
# Wrapper script for cron execution
cd "$(dirname "$0")"
source venv/bin/activate
python3 monitor.py >> monitor.log 2>&1
