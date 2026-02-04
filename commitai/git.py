# -*- coding: utf-8 -*-
import os
import subprocess
from typing import Optional


def get_repository_name() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        .strip()
        .decode()
    )


def get_current_branch_name() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        .strip()
        .decode()
    )


def get_staged_changes_diff() -> str:
    return subprocess.check_output(["git", "diff", "--staged"]).decode()


def stage_all_changes() -> None:
    subprocess.run(["git", "add", "--all"])


def create_commit(message: str) -> None:
    subprocess.run(["git", "commit", "-m", message])


def run_pre_commit_hook() -> bool:
    repo_path = get_repository_name()
    pre_commit_path = os.path.join(repo_path, ".git", "hooks", "pre-commit")
    if os.path.exists(pre_commit_path) and os.access(pre_commit_path, os.X_OK):
        try:
            subprocess.check_call(pre_commit_path)
            return True
        except subprocess.CalledProcessError:
            return False
    return True


def get_commit_template() -> Optional[str]:
    repo_path = get_repository_name()
    template_path = os.path.join(repo_path, ".git", "commit_template.txt")
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            return f.read()
    return os.getenv("TEMPLATE_COMMIT")


def save_commit_template(template: str) -> None:
    repo_path = get_repository_name()
    template_path = os.path.join(repo_path, ".git", "commit_template.txt")
    with open(template_path, "w") as f:
        f.write(template)


def get_unstaged_files() -> list[str]:
    """Returns a list of files that are modified/untracked but not staged."""
    # Modified files
    modified = (
        subprocess.check_output(["git", "diff", "--name-only"])
        .strip()
        .decode()
        .splitlines()
    )
    # Untracked files
    untracked = (
        subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"])
        .strip()
        .decode()
        .splitlines()
    )
    # Filter empty strings
    return [f for f in modified + untracked if f]


def stage_file(file_path: str) -> None:
    """Stages a specific file."""
    subprocess.run(["git", "add", file_path], check=True)
