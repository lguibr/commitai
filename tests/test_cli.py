# File: commitai/tests/test_cli.py
# -*- coding: utf-8 -*-
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click import UsageError
from click.testing import CliRunner
from langchain_google_genai import (
    ChatGoogleGenerativeAI as ActualChatGoogleGenerativeAI,
)

from commitai.cli import cli


# Fixture to mock external dependencies for generate_message
@pytest.fixture
def mock_generate_deps(tmp_path):
    fake_repo_path = tmp_path / "fake-repo"
    fake_repo_path.mkdir()
    fake_git_dir = fake_repo_path / ".git"
    fake_commit_msg_path = str(fake_git_dir / "COMMIT_EDITMSG")

    mock_file_open_patch = patch("builtins.open", mock_open())

    with (
        patch(
            "commitai.cli.ChatGoogleGenerativeAI",
            spec=ActualChatGoogleGenerativeAI,
            create=True,
        ) as mock_google_class_in_cli,
        patch("commitai.cli.stage_all_changes") as mock_stage,
        patch("commitai.cli.run_pre_commit_hook", return_value=True) as mock_hook,
        patch(
            "commitai.cli.get_staged_changes_diff", return_value="Staged changes diff"
        ) as mock_diff,
        patch(
            "commitai.cli.get_repository_name", return_value=str(fake_repo_path)
        ) as mock_repo,
        patch(
            "commitai.cli.get_current_branch_name", return_value="main"
        ) as mock_branch,
        patch("commitai.cli.create_commit") as mock_commit,
        # Update mock target for agent creation
        patch("commitai.cli.create_commit_agent") as mock_create_agent,
        patch("click.edit") as mock_edit,
        patch("click.clear"),
        patch(
            "commitai.cli._get_google_api_key", return_value="fake_google_key"
        ) as mock_get_google_key,
        patch("os.getenv") as mock_getenv,
        patch("os.makedirs") as mock_makedirs,
        mock_file_open_patch as mock_builtin_open,
        patch("os.path.exists") as mock_path_exists,
        patch("commitai.ui.RichUI") as mock_ui_class,
    ):  # Mock os.path.exists
        mock_path_exists.return_value = False

        mock_google_instance = mock_google_class_in_cli.return_value

        # Agent Mock (RunnableLambda now)
        mock_agent_runnable = MagicMock()
        mock_agent_runnable.stream.return_value = iter(
            [{"type": "token", "content": "Generated commit message"}]
        )
        mock_create_agent.return_value = mock_agent_runnable

        if mock_google_class_in_cli is not None:
            mock_google_instance.spec = ActualChatGoogleGenerativeAI

        content_mock = MagicMock()
        content_mock.content = "Generated commit message"
        mock_google_instance.invoke.return_value = content_mock

        # Setup Rich UI Mock
        mock_ui_instance = mock_ui_class.return_value
        # Default behavior for interactive staging
        # (False means nothing staged, proceed normally if add=True or check diff)
        mock_ui_instance.interactive_staging.return_value = False
        mock_ui_instance.confirm_action.return_value = True
        mock_ui_instance.stream_response.return_value = "Generated commit message"

        def getenv_side_effect(key, default=None):
            if key == "TEMPLATE_COMMIT":
                return None
            return os.environ.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        yield {
            "google_class": mock_google_class_in_cli,
            "google_instance": mock_google_instance,
            "stage": mock_stage,
            "hook": mock_hook,
            "diff": mock_diff,
            "repo": mock_repo,
            "branch": mock_branch,
            "commit": mock_commit,
            "edit": mock_edit,
            "getenv": mock_getenv,
            "get_google_key": mock_get_google_key,
            "makedirs": mock_makedirs,
            "file_open": mock_builtin_open,
            "path_exists": mock_path_exists,
            "commit_msg_path": fake_commit_msg_path,
            "create_agent": mock_create_agent,
            "agent_instance": mock_agent_runnable,
            "ui": mock_ui_instance,  # Access mock UI
        }


# --- Test generate command ---


def test_generate_default_gemini(mock_generate_deps):
    """Test the generate command defaults to gemini-3-flash-preview."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"

    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    # We can't rely on exit code easily if sys.exit was called by UI print_error
    # But here we expect success (exit code 0)
    assert result.exit_code == 0, result.output

    # Check that Flash was initialized
    mock_generate_deps["google_class"].assert_called_with(
        model="gemini-3-flash-preview",
        google_api_key="fake_google_key",
        streaming=True,
    )
    mock_generate_deps["agent_instance"].stream.assert_called_once()
    mock_generate_deps["commit"].assert_called_once_with("Generated commit message")
    mock_generate_deps["ui"].render_header.assert_called_once()


def test_generate_deep_flag(mock_generate_deps):
    """Test the --deep flag upgrades to gemini-3-pro-preview."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"

    result = runner.invoke(
        cli, ["generate", "--no-review", "--deep", "Test explanation"]
    )

    assert result.exit_code == 0, result.output

    # Check that Pro was initialized
    mock_generate_deps["google_class"].assert_called_with(
        model="gemini-3-pro-preview",
        google_api_key="fake_google_key",
        streaming=True,
    )


def test_generate_unsupported_model(mock_generate_deps):
    """Test that unsupported models raise an error in click validation/init logic."""
    # Since check is done in _initialize_llm which raises ClickException,
    # runner captures it.
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--no-review", "-m", "gpt-4"])

    assert result.exit_code == 1
    assert "Unsupported model: gpt-4" in result.output


def test_generate_with_add_flag(mock_generate_deps):
    """Test the -a flag with generate command."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(cli, ["generate", "--no-review", "-a", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["stage"].assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_commit_flag(mock_generate_deps):
    """Test the -c flag with generate command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--no-review", "-c", "Test explanation"])

    assert result.exit_code == 0, result.output
    # UI actions are bypassed for confirmation?
    # No, cli.py logic: if commit=True, pass commit=True to _handle_commit
    # _handle_commit logic: if not commit_flag: show confirmation loop.
    # So if commit=True, it skips confirmation loop.

    mock_generate_deps["ui"].confirm_action.assert_not_called()

    commit_msg_path = mock_generate_deps["commit_msg_path"]
    mock_generate_deps["file_open"].assert_called_once_with(commit_msg_path, "w")
    mock_generate_deps["file_open"].return_value.write.assert_called_once_with(
        "Generated commit message"
    )
    mock_generate_deps["commit"].assert_called_once_with("Generated commit message")


def test_generate_no_staged_changes(mock_generate_deps):
    """Test generate command with no staged changes."""
    mock_generate_deps["diff"].return_value = ""
    runner = CliRunner()

    # Click Runner catches sys.exit(1)
    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1, result.output
    mock_generate_deps["ui"].print_error.assert_called_with(
        "⚠️ Warning: No staged changes found. Exiting."
    )

    mock_generate_deps["agent_instance"].stream.assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


def test_generate_pre_commit_hook_fails(mock_generate_deps):
    """Test generate command when pre-commit hook fails."""
    mock_generate_deps["hook"].return_value = False
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Pre-commit hook failed. Aborting commit."
    )
    mock_generate_deps["diff"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


def test_generate_missing_google_key(mock_generate_deps):
    """Test generate command with missing Google API key."""
    # Reset both side_effect and return_value
    mock_generate_deps["get_google_key"].side_effect = None
    mock_generate_deps["get_google_key"].return_value = None

    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1
    assert "Google API Key not found" in result.output
    mock_generate_deps["google_class"].assert_not_called()


def test_generate_empty_commit_message_aborts(mock_generate_deps):
    """Test generate command aborts with empty commit message."""
    runner = CliRunner()
    # Simulate streaming returns empty string?
    # Or result is empty string.
    mock_generate_deps["ui"].stream_response.return_value = ""

    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    # Code calls: sys.exit(1) inside _handle_commit if final is empty
    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Aborting commit due to empty commit message."
    )


def test_generate_no_explanation(mock_generate_deps):
    """Test generate command without an explanation."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(cli, ["generate", "--no-review"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["agent_instance"].stream.assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_global_template(mock_generate_deps):
    """Test generate command with a global template."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    mock_generate_deps["path_exists"].return_value = False
    original_getenv = mock_generate_deps["getenv"].side_effect

    def getenv_side_effect_with_template(key, default=None):
        if key == "TEMPLATE_COMMIT":
            return "Global Template Instruction."
        return (
            original_getenv(key, default)
            if callable(original_getenv)
            else os.environ.get(key, default)
        )

    mock_generate_deps["getenv"].side_effect = getenv_side_effect_with_template

    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])
    assert result.exit_code == 0, result.output

    # Verify agent invocation has correct args
    call_args = mock_generate_deps["agent_instance"].stream.call_args
    assert call_args is not None, "agent invoke was not called"
    invoked_args = call_args[0][0]
    assert invoked_args["explanation"] == "Test explanation"

    mock_generate_deps["commit"].assert_called_once()


# Patch get_commit_template directly for this test
@patch("commitai.cli.get_commit_template")
def test_generate_with_local_template(mock_get_template, mock_generate_deps):
    """Test generate command local template file by mocking get_commit_template."""
    runner = CliRunner()
    local_template_content = "Local Template Instruction."
    # Configure the mock to return the local template content
    mock_get_template.return_value = local_template_content
    # Ensure read after edit works
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_get_template.assert_called_once()  # Verify get_commit_template was called
    # Verify agent invocation has correct args
    call_args = mock_generate_deps["agent_instance"].stream.call_args
    assert call_args is not None, "agent invoke was not called"
    invoked_args = call_args[0][0]
    assert invoked_args["explanation"] == "Test explanation"
    assert invoked_args["template"] == local_template_content
    assert "Global Template Instruction." not in invoked_args.get(
        "template", ""
    )  # Check global wasn't used (mock getenv)
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_deprecated_template_option(mock_generate_deps):
    """Test generate command with deprecated --template option."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    mock_generate_deps["path_exists"].return_value = False

    result = runner.invoke(
        cli,
        ["generate", "--no-review", "-t", "Deprecated Template", "Test explanation"],
    )

    assert result.exit_code == 0, result.output
    # UI verification
    mock_generate_deps["ui"].console.print.assert_any_call(
        "[warning]⚠️ --template/-t is deprecated.[/warning]"
    )
    mock_generate_deps["agent_instance"].stream.assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_edit_error_usage(mock_generate_deps):
    """Test generate command handling UsageError during click.edit."""
    runner = CliRunner()
    # Mock confirm flow in _handle_commit:
    # prompt "Commit...?" -> False
    # prompt "Edit...?" -> True
    mock_generate_deps["ui"].confirm_action.side_effect = [False, True]
    mock_generate_deps["edit"].side_effect = UsageError("Cannot find editor")

    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Could not open editor: Cannot find editor"
    )

    # Continue to commit old message if edit fails?
    # Current code: exceptions caught, loop finishes (or raises?)
    # If edit raises UsageError, we print error, then what?
    # Loop ends?
    # The code:
    # else:
    #    if ui.confirm_action("Edit message manually?"):
    #        try: ... except UsageError: print_error
    # Does it recursively call or exit?
    # It catches, does nothing else.
    # Then final_commit_message check -> proceeds.

    mock_generate_deps["commit"].assert_called_once_with("Generated commit message")


def test_generate_edit_error_io(mock_generate_deps):
    """Test generate command handling IOError during reading after click.edit."""
    runner = CliRunner()
    mock_generate_deps["ui"].confirm_action.side_effect = [False, True]

    # Simulate read failing on the specific handle for COMMIT_EDITMSG
    mock_generate_deps["file_open"].return_value.read.side_effect = IOError(
        "Read permission denied"
    )

    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Error handling user input: Read permission denied"
    )
    mock_generate_deps["commit"].assert_not_called()


def test_generate_write_error_io(mock_generate_deps):
    """Test generate command handling IOError during writing COMMIT_EDITMSG."""
    runner = CliRunner()
    commit_msg_path = mock_generate_deps["commit_msg_path"]

    def write_fail_side_effect(path, mode="r", *args, **kwargs):
        if str(path) == commit_msg_path and mode == "w":
            raise IOError("Write permission denied")
        return mock_open()()

    mock_generate_deps["file_open"].side_effect = write_fail_side_effect

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Error writing commit message file: Write permission denied"
    )
    mock_generate_deps["edit"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


@patch("commitai.cli.ChatGoogleGenerativeAI", None)
def test_generate_google_module_not_installed(mock_generate_deps):
    """Test generate command error when google module not installed."""
    runner = CliRunner()
    mock_generate_deps["google_class"] = None
    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1
    assert "'langchain-google-genai' is not installed" in result.output


def test_generate_llm_invoke_error(mock_generate_deps):
    """Test generate command handling error during llm.invoke."""
    runner = CliRunner()
    mock_generate_deps["agent_instance"].stream.side_effect = Exception("AI API Error")
    result = runner.invoke(cli, ["generate", "--no-review", "Test explanation"])

    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Error during AI generation: AI API Error"
    )
    mock_generate_deps["commit"].assert_not_called()


def test_generate_makedirs_error(mock_generate_deps):
    """Test generate command handling error during os.makedirs."""
    runner = CliRunner()
    mock_generate_deps["makedirs"].side_effect = OSError("Permission denied")

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1
    mock_generate_deps["ui"].print_error.assert_called_with(
        "Error creating .git directory: Permission denied"
    )
    mock_generate_deps["file_open"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


# --- Test create-template command ---


def test_create_template_command():
    """Test the create-template command."""
    runner = CliRunner()
    with patch("commitai.cli.save_commit_template") as mock_save_template:
        # We need to patch the UI locally inside the command if imported there
        with patch("commitai.ui.RichUI") as mock_ui_class:
            result = runner.invoke(cli, ["create-template", "Test template content"])
            assert result.exit_code == 0

            mock_save_template.assert_called_once_with("Test template content")
            mock_ui_class.return_value.print_success.assert_called_with(
                "Template saved successfully."
            )


def test_create_template_command_no_content():
    """Test the create-template command with no content."""
    runner = CliRunner()
    with patch("commitai.cli.save_commit_template") as mock_save_template:
        with patch("commitai.ui.RichUI") as mock_ui_class:
            result = runner.invoke(cli, ["create-template"])
            assert result.exit_code == 0
            mock_save_template.assert_not_called()
            mock_ui_class.return_value.print_error.assert_called_with(
                "Please provide the template content."
            )
