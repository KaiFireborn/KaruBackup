# KaruBackup
Python scripts to automatically generate scheduled backup .sh jobs from a jsonc settings file (out-of-the-box currently only for linux)

## Requirements
Requires `python3` (with `pip`) and `cronie` (or alternatives for crontab -e) installed. You can enable cronie via `sudo systemctl enable --now cronie`

## Instructions
Ajust `jobs.jsonc` (according to the schema specified) and (re-)run `./start_generate.sh`. This will execute `./initial_setup.sh` if needed (to potentially install dependencies and ajust crontab to periodically execute `./run_overdue_backups.py`) and then `./generate_jobs_from_json.py`, which creates all scripts necessary for your jobs in `./generated/`. 

## Documentation
### Explanations:
- `jobs.jsonc` - main config. See jobs_syntax.txt for help.
- `generate_jobs_from_json.py` - generates jobs 
generated - the folder with generated job scripts and timestamp files. Do not alter since it's being overwritten anyway, but feel free to check the scripts. Perhaps something can be done better...
- `run_overdue_backups.py` - checks every job in `generated`, and runs it if it's overdue according to the jobs config. 
- `initial_setup.sh` - RUN THIS FILE FIRST (only needed once). Sets up a cron job that triggers the above script every 10 minutes (you can alter the interval, but it should't be shorter than your job intervals - otherwise the jobs won't be on time)
- `./start_generate.sh` - runs `./generate_jobs_from_json.py` and `./initial_setup.sh` if not run before.
