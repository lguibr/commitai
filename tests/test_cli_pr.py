import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from commitai.cli.main import cli
from commitai.types import TemplateType


def test_pr_command():
    runner = CliRunner()

    with (
        patch("subprocess.check_output") as mock_check_output,
        patch("commitai.template.get_template") as mock_get_template,
        patch("commitai.agent.create_pr_agent") as mock_create_agent,
        patch("commitai.cli.main._initialize_llm"),
        patch("commitai.cli.main.RichUI") as mock_ui,
    ):
        mock_check_output.return_value = b"diff output"
        mock_get_template.return_value = "my pr template"

        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        mock_agent.stream.return_value = [{"output": "agent output"}]

        mock_ui_instance = mock_ui.return_value
        mock_ui_instance.stream_response.return_value = "streamed PR description"

        result = runner.invoke(cli, ["pr", "test", "feedback", "-b", "main"])

        assert result.exit_code == 0
        mock_check_output.assert_called()
        mock_get_template.assert_called_with(TemplateType.PR)
        mock_ui_instance.stream_response.assert_called_once()
        mock_ui_instance.console.print.assert_called()


def test_pr_command_no_diff():
    runner = CliRunner()

    with (
        patch("subprocess.check_output") as mock_check_output,
        patch("commitai.cli.main.RichUI") as mock_ui,
        patch("commitai.cli.main._initialize_llm"),
    ):
        mock_check_output.return_value = b""  # No diff

        result = runner.invoke(cli, ["pr", "test", "feedback", "-b", "main"])

        assert result.exit_code == 1
        mock_ui.return_value.print_error.assert_called()


def test_pr_command_subprocess_error():
    runner = CliRunner()

    with (
        patch("subprocess.check_output") as mock_check_output,
        patch("commitai.cli.main.RichUI") as mock_ui,
        patch("commitai.cli.main._initialize_llm"),
    ):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "git diff")

        result = runner.invoke(cli, ["pr", "test", "feedback", "-b", "main"])

        assert result.exit_code == 1
        mock_ui.return_value.print_error.assert_called()


def test_manage_templates_exit():
    runner = CliRunner()
    with (
        patch("questionary.select") as mock_questionary_select,
        patch("commitai.cli.main.RichUI"),
    ):
        mock_questionary_select.return_value.ask.return_value = "Exit"
        result = runner.invoke(cli, ["manage-templates"])
        assert result.exit_code == 0


def test_manage_templates_view():
    runner = CliRunner()
    with (
        patch("questionary.select") as mock_questionary_select,
        patch("commitai.template.get_template") as mock_get_template,
        patch("commitai.cli.main.RichUI") as mock_ui,
    ):
        mock_questionary_select.return_value.ask.side_effect = [
            "Commit Template",
            "View",
        ]
        mock_get_template.return_value = "Template content"

        result = runner.invoke(cli, ["manage-templates"])

        assert result.exit_code == 0
        mock_get_template.assert_called_with(TemplateType.COMMIT)
        mock_ui.return_value.console.print.assert_called()


def test_manage_templates_edit():
    runner = CliRunner()
    with (
        patch("questionary.select") as mock_questionary_select,
        patch("commitai.template.get_template") as mock_get_template,
        patch("commitai.template.save_template") as mock_save_template,
        patch("click.edit") as mock_click_edit,
        patch("commitai.cli.main.RichUI") as mock_ui,
    ):
        mock_questionary_select.return_value.ask.side_effect = [
            "Pull Request Template",
            "Edit",
        ]
        mock_get_template.return_value = "Template content"
        mock_click_edit.return_value = "New Template content"

        result = runner.invoke(cli, ["manage-templates"])

        assert result.exit_code == 0
        mock_save_template.assert_called_with(TemplateType.PR, "New Template content")
        mock_ui.return_value.print_success.assert_called()


def test_manage_templates_delete():
    runner = CliRunner()
    with (
        patch("questionary.select") as mock_questionary_select,
        patch("commitai.template.delete_template") as mock_delete_template,
        patch("commitai.cli.main.RichUI") as mock_ui,
    ):
        mock_questionary_select.return_value.ask.side_effect = [
            "Commit Template",
            "Delete",
        ]

        result = runner.invoke(cli, ["manage-templates"])

        assert result.exit_code == 0
        mock_delete_template.assert_called_with(TemplateType.COMMIT)
        mock_ui.return_value.print_success.assert_called()
