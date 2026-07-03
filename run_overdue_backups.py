import os
import time
import subprocess

# Executes OVERDUE job scripts in generated; Intended to be called by a systemd timer at intervals (preferably shorter than job intervals).

current_timestamp = time.time()
base_dir = "generated"


def read_mark_contents(filename):
    with open(filename, "r") as outfile:
        content = int(outfile.read().strip())
    return content


for job in os.listdir(base_dir):
    print("Checking", job)
    subfolder_path = os.path.join(base_dir, job)
    try:
        last_execution = read_mark_contents(
            os.path.join(subfolder_path, "last_executed_on.kf")
        )
        exec_interval = read_mark_contents(
            os.path.join(subfolder_path, "exec_every_n_sec.kf")
        )

        if exec_interval + last_execution < current_timestamp:
            print("Overdue!")
            scripts_to_execute = ["copy.sh", "remember_current_timestamp.sh"]
            for script in scripts_to_execute:
                script_path = os.path.join(os.path.join(subfolder_path, script))
                if os.path.exists(script_path):
                    subprocess.run(script_path, check=True)
            print("Job scripts ran.")
    except Exception as e:
        print("Fail.", e)
        continue
