# -*- coding: utf-8 -*-
import os
import tempfile
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from commitai.cli import cli


def test_generate_message_command():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "test-repo")
        os.makedirs(repo_path)
        git_path = os.path.join(repo_path, ".git")
        os.makedirs(git_path)

        with (
            patch("commitai.cli.ChatOpenAI") as mock_openai,
            patch("commitai.cli.ChatAnthropic") as mock_anthropic,
            patch("commitai.cli.stage_all_changes"),
            patch("commitai.cli.run_pre_commit_hook"),
            patch("commitai.cli.get_staged_changes_diff") as mock_get_diff,
            patch("commitai.cli.get_repository_name") as mock_get_repo_name,
            patch(
                "commitai.cli.get_current_branch_name"
            ) as mock_get_branch_name,  # noqa
            patch("commitai.cli.get_commit_template"),
            patch("commitai.cli.create_commit"),
        ):
            content_mock = MagicMock(content="Generated commit message")
            mock_openai.return_value.invoke.return_value = content_mock
            mock_anthropic.return_value.invoke.return_value = content_mock

            mock_get_diff.return_value = "Staged changes diff"
            mock_get_repo_name.return_value = repo_path
            mock_get_branch_name.return_value = "main"

            result = runner.invoke(cli, ["commitai", "Test explanation"])
            assert "Generated commit message" in result.output


def test_create_template_command():
    runner = CliRunner()
    with patch("commitai.cli.save_commit_template") as mock_save_template:
        result = runner.invoke(cli, ["create-template", "Test template"])
        assert result.exit_code == 0
        mock_save_template.assert_called_once_with("Test template")
        assert "Template saved successfully." in result.output

    result = runner.invoke(cli, ["create-template"])
    assert result.exit_code == 0
    assert "Please provide the template content." in result.output


def test_commitai_command():
    runner = CliRunner()
    with (
        patch("commitai.cli.generate_message") as mock_generate_message,
        patch("commitai.cli.stage_all_changes") as mock_stage_changes,
    ):
        result = runner.invoke(
            cli,
            ["commitai", "Test explanation"],
        )
        assert result.exit_code == 0
        mock_generate_message.assert_called_once_with(
            description=("Test explanation",), add=False, commit=True
        )

        result = runner.invoke(cli, ["commitai", "-a"])
        assert result.exit_code == 0
        mock_stage_changes.assert_called_once()
        mock_generate_message.assert_called_with(
            description=(),
            add=True,
            commit=True,
        )


def test_commitai_create_template_command():
    runner = CliRunner()
    with patch("commitai.cli.create_template_command") as mock_create_template:
        result = runner.invoke(
            cli,
            ["commitai-create-template", "Test template"],
        )
        assert result.exit_code == 0
        mock_create_template.assert_called_once_with(
            template_content=("Test template",)
        )
