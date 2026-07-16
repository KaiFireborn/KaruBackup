import json5
import subprocess
import os
import shutil
import traceback

APP_NAME = "KaruBackup"
ACCEPTED_STYLE_MODES = ["custom", "rsync_basic", "rclone_basic", "restic_basic"]
INITIALLY_OVERDUE = True


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
    def processSource(source_dict):
        source_mountpoint = source_dict["mountpoint"]
        source_dir = source_mountpoint + source_dict["path_from_mountpoint"]

        if source_dir[-1] != "/":
            source_dir += "/"

        excluded = source_dict[
            "explicit_exclude"
        ]  # TODO: validation: all of these must be subdirectories of root_dir
        # checkAndWarnDirs(excluded, "Excluded", abort=False) FIXME: reenable
        excluded_dirs_total = (
            excluded  # + (all_dirs in root - included) # TODO: handle this
        )
        os.makedirs(f"./generated/{title}", exist_ok=True)
        excluded_dirs_file_abs_path = writeTextToFile(
            f"./generated/{title}/excluded_dirs.txt", "\n".join(excluded_dirs_total)
        )

        if "~" in source_dir:
            warn("Don't use ~ instead of /home/username/ in jobs.jsonc!", abort=True)
        return source_dir, source_mountpoint, excluded_dirs_file_abs_path

    def processRemote(remote_dict, style, job_name):
        remote_mountpoint = remote_dict["mountpoint"]
        remote_dir = remote_mountpoint + remote_dict["path_from_mountpoint"]
        os.makedirs(remote_dir, exist_ok=True)
        if "~" in remote_dir:
            warn("Don't use ~ instead of /home/username/ in jobs.jsonc!", abort=True)
        return remote_dir, remote_mountpoint

    def processPrecommand(precommand):
        return precommand  # TODO: validate this somehow

    def processPostcommand(postcommand):
        return postcommand  # TODO: validate this somehow

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
        if style["mode"] not in ACCEPTED_STYLE_MODES:
            warn(f"No style {style['mode']} found.", abort=True)
        return style

    def processCategory(category):
        return category

    def generateVerificationFiles(
        source_dir, source_mountpoint, remote_dir, remote_mountpoint, job_name, category
    ):
        generated_folder = f"./generated/{job_name}/"
        os.makedirs(generated_folder, exist_ok=True)
        exclude_file = generated_folder + "excluded_dirs.txt"
        with open("templates/verify.sh", "r") as infile:
            script = infile.read().format(
                source_dir, remote_dir, job_name, exclude_file
            )

        writeTextToFile(generated_folder + "verify.sh", script)

    def generateTimerHelperFiles(job_name, manual_only, on_update, interval_minutes):
        generated_folder = f"./generated/{job_name}/"
        os.makedirs(generated_folder, exist_ok=True)

        if manual_only:
            writeTextToFile(generated_folder + "MANUAL_ONLY.kf", "")

        timemark_marker_filename = "last_executed_on.kf"
        timemark_content = f"""#!/bin/sh
date +%s > {generated_folder}{timemark_marker_filename}
        """
        timemark_script_filename = "remember_current_timestamp.sh"
        writeTextToFile(generated_folder + timemark_script_filename, timemark_content)
        subprocess.run(["chmod", "+x", generated_folder + timemark_script_filename])

        if INITIALLY_OVERDUE:
            writeTextToFile(generated_folder + timemark_marker_filename, "0")
        else:
            subprocess.run([generated_folder + timemark_script_filename])

        interval_content = str(interval_minutes * 60)  # to unix timestamp format
        interval_filename = "exec_every_n_sec.kf"
        writeTextToFile(generated_folder + interval_filename, interval_content)

    def generateMainCommand(style_data, excluded_dirs_abs_path, source_dir, remote_dir):
        if style_data["mode"] == "rsync_basic":
            return f"rsync -a --info=progress2 --exclude-from='{excluded_dirs_abs_path}' {source_dir} {remote_dir}"
        elif style_data["mode"] == "rclone_basic":
            return ""  # TODO
        elif style_data["mode"] == "restic_basic":
            raise NotImplementedError
        elif style_data["mode"] == "custom":
            custom_command = style_data["additional"].format(
                excluded_dirs_abs_path=excluded_dirs_abs_path,
                source_dir=source_dir,
                remote_dir=remote_dir,
            )
            return custom_command

    def generateNotificationCommand(kind, content):
        return f"""notify-send -a "{APP_NAME}" -t 5100 "{APP_NAME} - {kind}" "{content}" 
        """

    def getEnvVariablesForNotifs():
        return f"""# formatting
YW='\033[1;33m'
NC='\033[0m'
export DISPLAY=:0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{os.getuid()}/bus
        """

    def generateCopyJob(
        source_dir,
        source_mountpoint,
        remote_dir,
        remote_mountpoint,
        job_name,
        category,
        precommand,
        maincommand,
        postcommand,
        style_data,
        excluded_dirs_abs_path,
    ):
        script = f"""#!/bin/bash
# {style_data["mode"]}

{getEnvVariablesForNotifs()}

#job
echo "${{YW}}-=- STARTING SYNC JOB -=-${{NC}}"
START_TIME=$(date +%s)

{generateNotificationCommand(style_data["mode"], f"{job_name} started. From {source_dir} to {remote_dir}")}

{precommand}
printf "${{YW}}-=- Precommand ran.${{NC}}"
{maincommand}
echo "${{YW}}-=- Maincommand ran.${{NC}}"
{postcommand}
printf "${{YW}}-=- Postcommand ran.${{NC}}"

# calculate time elapsed
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MIN=$((DURATION / 60))
SEC=$((DURATION % 60))
echo ""
echo "${{YW}}-=- SYNC JOB FINISHED IN ${{MIN}}min ${{SEC}}sec -=-${{NC}}"
{generateNotificationCommand(style_data["mode"], f"{job_name} finished in $MIN min $SEC sec")}
        """  # TODO: improve final notification with number of copied files and so on
        # precommand; match style: rsync from source to remote recursive, minimal, progress
        os.makedirs(f"./generated/{job_name}/", exist_ok=True)
        filename = f"./generated/{job_name}/copy.sh"
        writeTextToFile(filename, script)
        subprocess.run(["chmod", "+x", filename])

    category = processCategory(job["category"])
    style_data = processStyle(job["style"])
    source_dir, source_mountpoint, excluded_dirs_abs_path = processSource(job["source"])
    remote_dir, remote_mountpoint = processRemote(job["remote"], style_data, title)
    precommand = processPrecommand(job["precommand"])
    maincommand = generateMainCommand(
        style_data, excluded_dirs_abs_path, source_dir, remote_dir
    )
    postcommand = processPostcommand(job["postcommand"])
    manual_only, on_update, interval = processTrigger(job["trigger"])
    generateCopyJob(
        source_dir,
        source_mountpoint,
        remote_dir,
        remote_mountpoint,
        title,
        category,
        precommand,
        maincommand,
        postcommand,
        style_data,
        excluded_dirs_abs_path,
    )
    generateTimerHelperFiles(title, manual_only, on_update, interval)
    generateVerificationFiles(
        source_dir, source_mountpoint, remote_dir, remote_mountpoint, title, category
    )


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
