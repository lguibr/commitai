# -*- coding: utf-8 -*-
from unittest.mock import mock_open, patch

from commitai.git import (
    create_commit,
    get_commit_template,
    get_current_branch_name,
    get_repository_name,
    get_staged_changes_diff,
    run_pre_commit_hook,
    save_commit_template,
    stage_all_changes,
)


def test_get_repository_name():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"/path/to/repo\n"
        assert get_repository_name() == "/path/to/repo"


def test_get_current_branch_name():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = b"main\n"
        assert get_current_branch_name() == "main"


def test_get_staged_changes_diff():
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = (
            b"diff --git a/file1.txt b/file1.txt"
            b"\nindex 1234567..abcdefg 100644\n"
            b"--- a/file1.txt\n+++ b/file1.txt"
            b"\n@@ -1,2 +1,2 @@\n-old content\n+new content"
        )
        expected_output = (
            "diff --git a/file1.txt b/file1.txt"
            "\nindex 1234567..abcdefg 100644\n"
            "--- a/file1.txt\n+++ b/file1.txt\n@@ -1,2 +1,2 @@"
            "\n-old content\n+new content"
        )
        assert get_staged_changes_diff() == expected_output


def test_stage_all_changes():
    with patch("subprocess.run") as mock_run:
        stage_all_changes()
        mock_run.assert_called_once_with(["git", "add", "--all"])


def test_create_commit():
    with patch("subprocess.run") as mock_run:
        create_commit("Test commit message")
        mock_run.assert_called_once_with(
            [
                "git",
                "commit",
                "-m",
                "Test commit message",
            ]
        )


def test_get_commit_template(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")
    template_path = git_path.join("commit_template.txt")
    template_path.write("Test template")

    with (
        patch("commitai.git.get_repository_name") as mock_get_repo_name,
        patch(
            "builtins.open",
            mock_open(read_data="Test template"),
            create=True,
        ),
    ):
        mock_get_repo_name.return_value = str(repo_path)
        assert get_commit_template() == "Test template"

    with (
        patch("os.getenv") as mock_getenv,
        patch(
            "builtins.open",
            mock_open(read_data="Global template"),
            create=True,
        ),
    ):
        mock_getenv.return_value = "Global template"
        assert get_commit_template() == "Global template"


def test_save_commit_template(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")

    with patch("commitai.git.get_repository_name") as mock_get_repo_name:
        mock_get_repo_name.return_value = str(repo_path)
        save_commit_template("Test template")
        template_path = git_path.join("commit_template.txt")
        assert template_path.read() == "Test template"


def test_run_pre_commit_hook(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")
    hooks_path = git_path.mkdir("hooks")
    pre_commit_path = hooks_path.join("pre-commit")
    pre_commit_path.write("#!/bin/sh\nexit 0")
    pre_commit_path.chmod(0o755)

    with patch("commitai.git.get_repository_name") as mock_get_repo_name:
        mock_get_repo_name.return_value = str(repo_path)
        assert run_pre_commit_hook() is True

    pre_commit_path.write("#!/bin/sh\nexit 1")
    with patch("commitai.git.get_repository_name") as mock_get_repo_name:
        mock_get_repo_name.return_value = str(repo_path)
        assert run_pre_commit_hook() is False
