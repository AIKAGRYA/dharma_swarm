import subprocess


def violation_dash_a():
    # ruleid: dharma.scripts-no-git-add-all
    subprocess.run(["git", "add", "-A"], check=True)


def violation_dot():
    # ruleid: dharma.scripts-no-git-add-all
    subprocess.run(["git", "add", "."], check=True)


def violation_shell_string():
    # ruleid: dharma.scripts-no-git-add-all
    subprocess.run("git add -A", shell=True)


def ok_specific_path():
    # ok: dharma.scripts-no-git-add-all
    subprocess.run(["git", "add", "src/specific.py"], check=True)


def ok_pathspec():
    # ok: dharma.scripts-no-git-add-all
    subprocess.run(["git", "add", "--", "src/"], check=True)
