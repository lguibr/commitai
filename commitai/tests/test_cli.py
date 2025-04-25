# File: commitai/tests/test_cli.py
# -*- coding: utf-8 -*-
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click import UsageError
from click.testing import CliRunner
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import (
    ChatGoogleGenerativeAI as ActualChatGoogleGenerativeAI,
)
from langchain_openai import ChatOpenAI

from commitai.cli import cli
from commitai.template import adding_template


# Fixture to mock external dependencies for generate_message
@pytest.fixture
def mock_generate_deps(tmp_path):
    fake_repo_path = tmp_path / "fake-repo"
    fake_repo_path.mkdir()
    fake_git_dir = fake_repo_path / ".git"
    fake_commit_msg_path = str(fake_git_dir / "COMMIT_EDITMSG")
    fake_template_path = str(fake_git_dir / "commit_template.txt")

    mock_file_open_patch = patch("builtins.open", mock_open())

    with (
        patch(
            "commitai.cli.ChatGoogleGenerativeAI",
            spec=ActualChatGoogleGenerativeAI,
            create=True,
        ) as mock_google_class_in_cli,
        patch("commitai.cli.ChatOpenAI", spec=ChatOpenAI) as mock_openai_class,
        patch("commitai.cli.ChatAnthropic", spec=ChatAnthropic) as mock_anthropic_class,
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
        patch("click.edit") as mock_edit,
        patch("click.clear"),
        patch(
            "commitai.cli._get_google_api_key", return_value="fake_google_key"
        ) as mock_get_google_key,
        patch("os.getenv") as mock_getenv,
        patch("os.makedirs") as mock_makedirs,
        mock_file_open_patch as mock_builtin_open,
        patch("os.path.exists") as mock_path_exists,
    ):  # Mock os.path.exists
        mock_path_exists.return_value = False

        mock_openai_instance = mock_openai_class.return_value
        mock_anthropic_instance = mock_anthropic_class.return_value
        mock_google_instance = mock_google_class_in_cli.return_value

        mock_openai_instance.spec = ChatOpenAI
        mock_anthropic_instance.spec = ChatAnthropic
        if mock_google_class_in_cli is not None:
            mock_google_instance.spec = ActualChatGoogleGenerativeAI

        content_mock = MagicMock()
        content_mock.content = "Generated commit message"
        mock_openai_instance.invoke.return_value = content_mock
        mock_anthropic_instance.invoke.return_value = content_mock
        mock_google_instance.invoke.return_value = content_mock

        def getenv_side_effect(key, default=None):
            if key == "OPENAI_API_KEY":
                return "fake_openai_key"
            if key == "ANTHROPIC_API_KEY":
                return "fake_anthropic_key"
            if key == "TEMPLATE_COMMIT":
                return None
            return os.environ.get(key, default)

        mock_getenv.side_effect = getenv_side_effect

        yield {
            "openai_class": mock_openai_class,
            "anthropic_class": mock_anthropic_class,
            "google_class": mock_google_class_in_cli,
            "openai_instance": mock_openai_instance,
            "anthropic_instance": mock_anthropic_instance,
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
            "repo_path": fake_repo_path,
            "commit_msg_path": fake_commit_msg_path,
            "template_path": fake_template_path,
        }


# --- Test generate command ---


def test_generate_default_gemini(mock_generate_deps):
    """Test the generate command defaults to gemini and no template."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    mock_generate_deps["path_exists"].return_value = False
    mock_generate_deps["getenv"].side_effect = lambda k, d=None: (
        None if k == "TEMPLATE_COMMIT" else os.environ.get(k, d)
    )

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["google_class"].assert_called_once_with(
        model="gemini-2.5-pro-preview-03-25",
        google_api_key="fake_google_key",
        temperature=0.7,
        convert_system_message_to_human=True,
    )
    call_args = mock_generate_deps["google_instance"].invoke.call_args
    assert call_args is not None
    prompt = call_args.kwargs["input"]
    assert adding_template not in prompt

    mock_generate_deps["google_instance"].invoke.assert_called_once()
    commit_msg_path = mock_generate_deps["commit_msg_path"]
    mock_generate_deps["file_open"].assert_any_call(commit_msg_path, "w")
    mock_generate_deps["file_open"].return_value.write.assert_called_with(
        "Generated commit message"
    )
    mock_generate_deps["edit"].assert_called_once_with(filename=commit_msg_path)
    mock_generate_deps["file_open"].assert_any_call(commit_msg_path, "r")
    mock_generate_deps["file_open"].return_value.read.assert_called()
    mock_generate_deps["commit"].assert_called_once_with("Generated commit message")


def test_generate_select_gpt4(mock_generate_deps):
    """Test selecting gpt-4 model via generate command."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(cli, ["generate", "-m", "gpt-4", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["openai_class"].assert_called_once_with(
        model="gpt-4", api_key="fake_openai_key", temperature=0.7
    )
    mock_generate_deps["openai_instance"].invoke.assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_select_claude(mock_generate_deps):
    """Test selecting claude model via generate command."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(
        cli, ["generate", "-m", "claude-3-opus-20240229", "Test explanation"]
    )

    assert result.exit_code == 0, result.output
    mock_generate_deps["anthropic_class"].assert_called_once_with(
        model_name="claude-3-opus-20240229",
        api_key="fake_anthropic_key",
        temperature=0.7,
    )
    mock_generate_deps["anthropic_instance"].invoke.assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_add_flag(mock_generate_deps):
    """Test the -a flag with generate command."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(cli, ["generate", "-a", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["stage"].assert_called_once()
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_commit_flag(mock_generate_deps):
    """Test the -c flag with generate command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-c", "Test explanation"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["edit"].assert_not_called()
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
    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "Warning: No staged changes found" in result.output
    mock_generate_deps["google_class"].assert_called_once()
    mock_generate_deps["google_instance"].invoke.assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


def test_generate_pre_commit_hook_fails(mock_generate_deps):
    """Test generate command when pre-commit hook fails."""
    mock_generate_deps["hook"].return_value = False
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "Pre-commit hook failed" in result.output
    mock_generate_deps["diff"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


def test_generate_missing_openai_key(mock_generate_deps):
    """Test generate command with missing OpenAI API key."""
    mock_generate_deps["getenv"].side_effect = lambda key, default=None: None
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-m", "gpt-4", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "OPENAI_API_KEY environment variable not set" in result.output
    mock_generate_deps["openai_class"].assert_not_called()


def test_generate_missing_anthropic_key(mock_generate_deps):
    """Test generate command with missing Anthropic API key."""
    mock_generate_deps["getenv"].side_effect = lambda key, default=None: None
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-m", "claude-3", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "ANTHROPIC_API_KEY environment variable not set" in result.output
    mock_generate_deps["anthropic_class"].assert_not_called()


def test_generate_missing_google_key(mock_generate_deps):
    """Test generate command with missing Google API key."""
    mock_generate_deps["get_google_key"].return_value = None
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-m", "gemini-pro", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "Google API Key not found" in result.output
    mock_generate_deps["google_class"].assert_not_called()


def test_generate_google_key_priority(mock_generate_deps):
    """Test Google API key priority with generate command."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"

    mock_generate_deps["get_google_key"].return_value = "genai_key"
    result = runner.invoke(cli, ["generate", "-m", "gemini-pro"])
    assert result.exit_code == 0, f"Run 1 failed: {result.output}"
    mock_generate_deps["google_class"].assert_called_with(
        model="gemini-pro",
        google_api_key="genai_key",
        temperature=0.7,
        convert_system_message_to_human=True,
    )
    mock_generate_deps["google_class"].reset_mock()
    mock_generate_deps["commit"].reset_mock()

    mock_generate_deps["get_google_key"].return_value = "gemini_key"
    result = runner.invoke(cli, ["generate", "-m", "gemini-pro"])
    assert result.exit_code == 0, f"Run 2 failed: {result.output}"
    mock_generate_deps["google_class"].assert_called_with(
        model="gemini-pro",
        google_api_key="gemini_key",
        temperature=0.7,
        convert_system_message_to_human=True,
    )
    mock_generate_deps["google_class"].reset_mock()
    mock_generate_deps["commit"].reset_mock()

    mock_generate_deps["get_google_key"].return_value = "google_key"
    result = runner.invoke(cli, ["generate", "-m", "gemini-pro"])
    assert result.exit_code == 0, f"Run 3 failed: {result.output}"
    mock_generate_deps["google_class"].assert_called_with(
        model="gemini-pro",
        google_api_key="google_key",
        temperature=0.7,
        convert_system_message_to_human=True,
    )


def test_generate_unsupported_model(mock_generate_deps):
    """Test generate command with an unsupported model."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["generate", "-m", "unsupported-model", "Test explanation"]
    )

    assert result.exit_code == 1, result.output
    assert "Unsupported model: unsupported-model" in result.output
    mock_generate_deps["commit"].assert_not_called()


def test_generate_empty_commit_message_aborts(mock_generate_deps):
    """Test generate command aborts with empty commit message after edit."""
    runner = CliRunner()
    # Simulate reading empty string after edit
    mock_generate_deps["file_open"].return_value.read.return_value = ""

    # Check exit code is 1
    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert (
        result.exit_code == 1
    ), f"Expected exit code 1, got {result.exit_code}. Output: {result.output}"
    # Check output for the specific error message (printed by Click's handler)
    assert "Aborting commit due to empty commit message" in result.output
    mock_generate_deps["commit"].assert_not_called()


def test_generate_no_explanation(mock_generate_deps):
    """Test generate command without an explanation."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    result = runner.invoke(cli, ["generate"])

    assert result.exit_code == 0, result.output
    mock_generate_deps["google_instance"].invoke.assert_called_once()
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

    result = runner.invoke(cli, ["generate", "Test explanation"])
    assert result.exit_code == 0, result.output
    call_args = mock_generate_deps["google_instance"].invoke.call_args
    assert call_args is not None, "invoke was not called"
    prompt = call_args.kwargs["input"]
    assert "Global Template Instruction." in prompt
    assert adding_template in prompt
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
    call_args = mock_generate_deps["google_instance"].invoke.call_args
    assert call_args is not None, "invoke was not called"
    prompt = call_args.kwargs["input"]
    assert (
        local_template_content in prompt
    ), f"Local template content not found in prompt:\n{prompt}"
    assert adding_template in prompt
    assert (
        "Global Template Instruction." not in prompt
    )  # Check global wasn't used (mock getenv)
    mock_generate_deps["commit"].assert_called_once()


def test_generate_with_deprecated_template_option(mock_generate_deps):
    """Test generate command with deprecated --template option."""
    runner = CliRunner()
    mock_generate_deps[
        "file_open"
    ].return_value.read.return_value = "Generated commit message"
    mock_generate_deps["path_exists"].return_value = False
    mock_generate_deps["getenv"].side_effect = lambda k, d=None: (
        None if k == "TEMPLATE_COMMIT" else os.environ.get(k, d)
    )

    result = runner.invoke(
        cli, ["generate", "-t", "Deprecated Template", "Test explanation"]
    )

    assert result.exit_code == 0, result.output
    assert "Warning: The --template/-t option is deprecated" in result.output
    call_args = mock_generate_deps["google_instance"].invoke.call_args
    assert call_args is not None, "invoke was not called"
    prompt = call_args.kwargs["input"]
    assert "Deprecated Template" in prompt
    assert adding_template in prompt
    mock_generate_deps["commit"].assert_called_once()


def test_generate_edit_error_usage(mock_generate_deps):
    """Test generate command handling UsageError during click.edit."""
    runner = CliRunner()
    mock_generate_deps["edit"].side_effect = UsageError("Cannot find editor")

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 0, result.output
    assert "Could not open editor: Cannot find editor" in result.output
    assert "Using generated message:" in result.output
    mock_generate_deps["commit"].assert_called_once_with("Generated commit message")


def test_generate_edit_error_io(mock_generate_deps):
    """Test generate command handling IOError during reading after click.edit."""
    runner = CliRunner()
    # Simulate read failing on the specific handle for COMMIT_EDITMSG
    mock_generate_deps["file_open"].return_value.read.side_effect = IOError(
        "Read permission denied"
    )

    # Check exit code is 1
    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert (
        result.exit_code == 1
    ), f"Expected exit code 1, got {result.exit_code}. Output: {result.output}"
    # Check output for the specific error message (printed by Click's handler)
    assert "Error reading commit message file after edit" in result.output
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

    assert result.exit_code == 1, result.output
    assert "Error writing commit message file" in result.output
    mock_generate_deps["edit"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


@patch("commitai.cli.ChatGoogleGenerativeAI", None)
def test_generate_google_module_not_installed(mock_generate_deps):
    """Test generate command error when google module not installed."""
    runner = CliRunner()
    mock_generate_deps["google_class"] = None
    result = runner.invoke(cli, ["generate", "-m", "gemini-pro", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "'langchain-google-genai' is not installed" in result.output


def test_generate_llm_invoke_error(mock_generate_deps):
    """Test generate command handling error during llm.invoke."""
    runner = CliRunner()
    mock_generate_deps["google_instance"].invoke.side_effect = Exception("AI API Error")

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "Error during AI generation: AI API Error" in result.output
    mock_generate_deps["commit"].assert_not_called()


def test_generate_makedirs_error(mock_generate_deps):
    """Test generate command handling error during os.makedirs."""
    runner = CliRunner()
    mock_generate_deps["makedirs"].side_effect = OSError("Permission denied")

    result = runner.invoke(cli, ["generate", "Test explanation"])

    assert result.exit_code == 1, result.output
    assert "Error creating .git directory: Permission denied" in result.output
    mock_generate_deps["file_open"].assert_not_called()
    mock_generate_deps["commit"].assert_not_called()


# --- Test create-template command ---


def test_create_template_command():
    """Test the create-template command."""
    runner = CliRunner()
    with patch("commitai.cli.save_commit_template") as mock_save_template:
        result = runner.invoke(cli, ["create-template", "Test template content"])
        assert result.exit_code == 0, result.output
        mock_save_template.assert_called_once_with("Test template content")
        assert "Template saved successfully." in result.output


def test_create_template_command_no_content():
    """Test the create-template command with no content."""
    runner = CliRunner()
    with patch("commitai.cli.save_commit_template") as mock_save_template:
        result = runner.invoke(cli, ["create-template"])
        assert result.exit_code == 0, result.output
        mock_save_template.assert_not_called()
        assert "Please provide the template content." in result.output
