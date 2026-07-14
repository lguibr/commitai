# File: commitai/tests/test_template.py
# -*- coding: utf-8 -*-

from unittest.mock import mock_open, patch

from commitai.template import (
    adding_template,
    build_user_message,
    default_system_message,
    delete_template,
    get_template,
    save_template,
)
from commitai.types import TemplateType


def test_build_user_message_with_explanation():
    """Test building the user message with both explanation and diff."""
    explanation = "This is the explanation."
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    expected_message = (
        f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"
    )
    actual_message = build_user_message(explanation, diff)
    assert actual_message == expected_message


def test_build_user_message_without_explanation():
    """Test building the user message with only the diff (empty explanation)."""
    explanation = ""
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    # When explanation is empty, the function should still include the prefix text
    expected_message = (
        f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"
    )
    actual_message = build_user_message(explanation, diff)
    assert actual_message == expected_message


def test_default_system_message_content():
    """Test that the default system message exists and is a non-empty string."""
    assert isinstance(default_system_message, str)
    assert len(default_system_message) > 0
    assert "conventional commit format" in default_system_message


def test_adding_template_content():
    """Test that the adding template constant exists and is a non-empty string."""
    assert isinstance(adding_template, str)
    assert len(adding_template) > 0
    assert "follow this template" in adding_template


def test_get_commit_template(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")
    template_path = git_path.join("commit_template.txt")
    template_path.write("Test template")

    with (
        patch("commitai.template.manager.get_repository_name") as mock_get_repo_name,
        patch(
            "builtins.open",
            mock_open(read_data="Test template"),
            create=True,
        ),
    ):
        mock_get_repo_name.return_value = str(repo_path)
        assert get_template(TemplateType.COMMIT) == "Test template"

    with (
        patch("os.getenv") as mock_getenv,
        patch(
            "builtins.open",
            mock_open(read_data="Global template"),
            create=True,
        ),
    ):
        mock_getenv.return_value = "Global template"
        assert get_template(TemplateType.COMMIT) == "Global template"


def test_save_commit_template(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")

    with patch("commitai.template.manager.get_repository_name") as mock_get_repo_name:
        mock_get_repo_name.return_value = str(repo_path)
        save_template(TemplateType.COMMIT, "Test template")
        template_path = git_path.join("commit_template.txt")
        assert template_path.read() == "Test template"


def test_delete_commit_template(tmpdir):
    repo_path = tmpdir.mkdir("repo")
    git_path = repo_path.mkdir(".git")
    template_path = git_path.join("commit_template.txt")
    template_path.write("Test template")

    with patch("commitai.template.manager.get_repository_name") as mock_get_repo_name:
        mock_get_repo_name.return_value = str(repo_path)
        delete_template(TemplateType.COMMIT)
        assert not template_path.exists()
