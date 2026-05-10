import os
import subprocess


def violation_skip_env():
    # ruleid: dharma.arjuna.no-warrant-bypass
    os.environ["DHARMA_SKIP_SHAKTI_WARRANT_GUARD"] = "1"


def violation_no_verify_args():
    # ruleid: dharma.arjuna.no-warrant-bypass
    subprocess.run(["git", "commit", "--no-verify", "-m", "skip"], check=False)


def violation_no_verify_shell():
    # ruleid: dharma.arjuna.no-warrant-bypass
    subprocess.run("git commit --no-verify", shell=True, check=False)


def ok_normal_commit():
    # ok: dharma.arjuna.no-warrant-bypass
    subprocess.run(["git", "commit", "-m", "use warrant"], check=False)


def ok_documentation_text():
    # ok: dharma.arjuna.no-warrant-bypass
    return "For emergency use only: git commit --no-verify."
