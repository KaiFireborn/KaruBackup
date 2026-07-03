#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OVERDUE_JOBS_SCRIPT="$SCRIPT_DIR/run_overdue_backups.py"

if [ -f "$OVERDUE_JOBS_SCRIPT" ]; then
    # /usr/bin/python3 "$OVERDUE_JOBS_SCRIPT"

    # add to crontab only if the script call is not yet there
    CRON_JOB="*/10 * * * * /usr/bin/python3 $OVERDUE_JOBS_SCRIPT"
    (crontab -l 2>/dev/null | grep -Fq "$OVERDUE_JOBS_SCRIPT") || (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    
else
    echo "Error: script to run not found at $OVERDUE_JOBS_SCRIPT" >&2
    exit 1
fi
