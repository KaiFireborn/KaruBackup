# KaruBackup
Python scripts to automatically generate scheduled backup .sh jobs from a jsonc settings file (out-of-the-box currently only for linux)

Requires python installed.

Explanations:

jobs.jsonc - main config. See jobs_syntax.txt for help.
generate_jobs_from_json.py - generates jobs 
generated - the folder with generated job scripts and timestamp files. Do not alter since it's being overwritten anyway, but feel free to check the scripts. Perhaps something can be done better...
run_overdue_backups.py - checks every job in `generated`, and runs it if it's overdue according to the jobs config. 
initial_setup.sh - RUN THIS FILE FIRST (only needed once). Sets up a cron job that triggers the above script every 10 minutes (you can alter the interval, but it should't be shorter than your job intervals - otherwise the jobs won't be on time)
