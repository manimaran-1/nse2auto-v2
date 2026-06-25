#!/bin/bash
# Script to run a single scan immediately and send results to Telegram.

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found."
    exit 1
fi

# Activate venv
source venv/bin/activate

# Execute manual scan
echo "----------------------------------------"
echo "🚀 Triggering Manual Scan Now..."
echo "Universe: $(grep SCAN_UNIVERSE config.py | cut -d'=' -f2 | tr -d ' "')"
echo "Interval: $(grep SCAN_INTERVAL config.py | cut -d'=' -f2 | tr -d ' "')"
echo "----------------------------------------"

# Run with TEST_RUN=1 and ONCE=1 to trigger immediate scan and exit
export TEST_RUN=1
export ONCE=1
python3 automation_bot.py

echo "----------------------------------------"
echo "✅ Manual scan complete."
echo "----------------------------------------"
