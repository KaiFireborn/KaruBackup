import json5
import subprocess
import os
import shutil
import traceback

APP_NAME = "KaruBackup"
ACCEPTED_STYLES = "rsync"


def readJson(filename):
    with open(filename, "r") as infile:
        return json5.load(infile)


def writeTextToFile(filename, text, append=False):
    with open(filename, "w+" if not append else "a+") as outfile:
        outfile.write(text)  # TODO: check this
    return os.path.abspath(filename)


def log(message):
    print(message)
    writeTextToFile("./log.txt", message + "\n", append=True)


def warn(warning, abort=False):
    log(warning)
    if abort:
        raise ValueError(warning)


def checkDir(path):
    if "~" in path:
        warn("Don't use ~ instead of /home/username/ in jobs.jsonc!", abort=True)
    return os.path.isfile(path) or os.path.isdir(path)


def checkAndWarnDirs(dirs, note, abort=False):
    messages = ""
    for dir in dirs:
        if not checkDir(dir):
            message = f"{note} {dir} is not valid directory.\n"
            messages += message
    if len(messages) > 0:
        warn(messages, abort=abort)


def getDirWeight(
    included, excluded
):  # something something about number of files or whatever
    pass


def processJob(title, job):
    def processSource(source):
        root_dir = source["root"]
        if root_dir[-1] != "/":
            root_dir += "/"
        checkAndWarnDirs([root_dir], "Root", abort=True)

        included = [root_dir + subdir for subdir in source["included_only"]]
        if (
            len(included) == 0
        ):  # TODO: check how rsync deals with this; potentially list all subdirs, subtract included, and add to excluded
            included = []  # TODO: get all dirs in root
        checkAndWarnDirs(included, "Included", abort=True)
        excluded = [
            root_dir + subdir for subdir in source["explicit_exclude"]
        ]  # TODO: validation: all of these must be subdirectories of root_dir
        checkAndWarnDirs(excluded, "Excluded", abort=False)

        excluded_dirs_total = (
            excluded  # + (all_dirs in root - included) # TODO: handle this
        )
        os.makedirs(f"./generated/{title}", exist_ok=True)
        excluded_dirs_file_abs_path = writeTextToFile(
            f"./generated/{title}/excluded_dirs.txt", "\n".join(excluded_dirs_total)
        )

        if "~" in root_dir:
            warn("Don't use ~ instead of /home/username/ in jobs.jsonc!", abort=True)
        return root_dir, excluded_dirs_file_abs_path

    def processRemote(remote, style, job_name):
        # TODO: especially handle on other disks/devices. What if something is mounted - how does rsync deal with copying from such dirs?
        os.makedirs(remote, exist_ok=True)  # hmm, create it and then check?
        checkAndWarnDirs(
            [remote], "Remote", abort=True
        )  # does it have to be connected to generate a job?? Destinations aren't always accessible
        remote_dir = f"{remote}{APP_NAME}/{style}/{job_name}/"
        os.makedirs(remote_dir, exist_ok=True)
        if "~" in remote_dir:
            warn("Don't use ~ instead of /home/username/ in jobs.jsonc!", abort=True)
        return remote_dir

    def processPrecommand(precommand):
        return precommand  # TODO: validate this somehow

    def processTrigger(trigger):
        # TODO: check what unit kron and stuff use, assuming seconds
        interval = trigger["every_n_units"]
        manual_only, on_update = False, False
        if trigger["every_n_units"] == -1:
            manual_only = True
        elif trigger["every_n_units"] == 0:
            on_update = True  # check how rsync can be made to watch for fiel changes?
        elif trigger["every_n_units"] > 0:
            match trigger["unit"]:
                case "minute":
                    interval *= 1
                case "hour":
                    interval *= 60
                case "day":
                    interval *= 60 * 24
                case "week":
                    interval *= 60 * 24 * 7
                case _:
                    warn(
                        f"Invalid schedule option unit: {trigger['unit']}, allowed minute/hour/day/week",
                        abort=True,
                    )
        else:
            warn(
                f"Invalid schedule option mode: {trigger['every_n_units']}, allowed -1 to +inf "
            )

        return manual_only, on_update, interval

    def processStyle(style):
        if style not in ACCEPTED_STYLES:
            warn(f"No style {style} found.", abort=True)
        return style

    def generateTimerHelperFiles(job_name, manual_only, on_update, interval_minutes):
        generated_folder = f"./generated/{job_name}/"
        os.makedirs(generated_folder, exist_ok=True)

        timemark_content = f"""#!/bin/sh
date +%s > {generated_folder}last_executed_on.kf
        """
        timemark_filename = "remember_current_timestamp.sh"
        writeTextToFile(generated_folder + timemark_filename, timemark_content)
        subprocess.run(["chmod", "+x", generated_folder + timemark_filename])
        subprocess.run([generated_folder + timemark_filename])

        interval_content = str(interval_minutes * 60)  # to unix timestamp format
        interval_filename = "exec_every_n_sec.kf"
        writeTextToFile(generated_folder + interval_filename, interval_content)

    def generateCopyJob(
        source_dir, remote_dir, job_name, precommand, style_data, excluded_dirs_abs_path
    ):
        script = f"""
        #!/bin/bash
         
        echo "-=- STARTING SYNC JOB -=-"
        START_TIME=$(date +%s)

        {precommand}
        echo "-=- Precommand ran."

        rsync -a --info=progress2 --exclude-from='{excluded_dirs_abs_path}' {source_dir} {remote_dir}
        
        # calculate time elapsed
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        MIN=$((DURATION / 60))
        SEC=$((DURATION % 60))
        echo ""
        echo "-=- SYNC JOB FINISHED IN ${{MIN}}min ${{SEC}}sec -=-"
        """
        # precommand; match style: rsync from source to remote recursive, minimal, progress
        os.makedirs(f"./generated/{job_name}/", exist_ok=True)
        filename = f"./generated/{job_name}/copy.sh"
        writeTextToFile(filename, script)
        subprocess.run(["chmod", "+x", filename])

    style_data = processStyle(job["style"])
    source_dir, excluded_dirs_abs_path = processSource(job["source"])
    remote_dir = processRemote(job["remote"], style_data, title)
    precommand = processPrecommand(job["precommand"])
    manual_only, on_update, interval = processTrigger(job["trigger"])
    # print(
    #     style_data, source_dir, remote_dir, precommand, manual_only, on_update, interval
    # )
    generateCopyJob(
        source_dir, remote_dir, title, precommand, style_data, excluded_dirs_abs_path
    )
    generateTimerHelperFiles(title, manual_only, on_update, interval)


def clearGeneratedFolder():
    folder = "./generated/"
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print("Failed to delete %s. Reason: %s" % (file_path, e))
    print("Cleared generated/ folder")


def listJobs(verbose=False):
    # for every folder in generated, check when the job last attempted and last succesful from its log, potentially with extra data
    # also list jobs from jobs.jsonc which were configured but failed to be generated
    pass  # TODO


def generate_job_files():
    clearGeneratedFolder()
    config = readJson("jobs.jsonc")
    for title, job in config["jobs"].items():
        try:
            processJob(title, job)
            print("Processed job", title)
        except Exception as e:
            print(f"AE: Generating job {title} failed!!!", e)
            traceback.print_exc()


if __name__ == "__main__":
    generate_job_files()
