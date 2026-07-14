from unittest.mock import MagicMock, patch

import pytest

from commitai.ui import RichUI


# Fixture for RichUI with mocked console
@pytest.fixture
def mock_ui():
    with patch("commitai.ui.core.console") as mock_console:
        ui = RichUI()
        ui.console = mock_console
        yield ui


def test_render_header_with_art(mock_ui):
    """Test header rendering when ASCII art file exists."""
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock) as mock_open,
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = "ASCII ART"

        mock_ui.render_header()

        mock_ui.console.clear.assert_called_once()
        # Verify it prints the panel with art
        assert mock_ui.console.print.call_count >= 1


def test_render_header_no_art(mock_ui):
    """Test header rendering fallback when ASCII art file is missing."""
    with patch("os.path.exists", return_value=False):
        mock_ui.render_header()

        mock_ui.console.clear.assert_called_once()
        # Should print fallback panel
        assert mock_ui.console.print.call_count >= 1


def test_interactive_staging_no_files(mock_ui):
    """Test interactive staging when no unstaged files exist."""
    with patch("commitai.ui.core.get_unstaged_files", return_value=[]):
        result = mock_ui.interactive_staging()
        assert result is False
        mock_ui.console.print.assert_not_called()


@patch("commitai.ui.core.get_unstaged_files", return_value=["file1.py", "file2.py"])
@patch("commitai.ui.core.questionary.checkbox")
def test_interactive_staging_selection(mock_checkbox, mock_get_files, mock_ui):
    """Test interactive staging with user selection."""
    # Mock user selecting one file
    mock_checkbox.return_value.ask.return_value = ["file1.py"]

    with patch("commitai.ui.core.stage_file") as mock_stage:
        result = mock_ui.interactive_staging()

        assert result is True
        mock_stage.assert_called_once_with("file1.py")
        mock_ui.console.print.assert_called()  # Should print success


@patch("commitai.ui.core.get_unstaged_files", return_value=["file1.py"])
@patch("commitai.ui.core.questionary.checkbox")
def test_interactive_staging_cancel(mock_checkbox, mock_get_files, mock_ui):
    """Test interactive staging when user cancels or selects nothing."""
    mock_checkbox.return_value.ask.return_value = []

    with patch("commitai.ui.core.stage_file") as mock_stage:
        result = mock_ui.interactive_staging()

        assert result is False
        mock_stage.assert_not_called()


def test_stream_response(mock_ui):
    """Test streaming response handling thought and token events."""
    # Mock events
    events = [
        {"type": "thought", "content": "Thinking..."},
        {"type": "token", "content": "Feat"},
        {"type": "token", "content": "ure"},
    ]

    # We need to mock Live because it's a context manager
    with patch("commitai.ui.core.Live") as mock_live_cls:
        mock_live_instance = mock_live_cls.return_value.__enter__.return_value

        final_content = mock_ui.stream_response(iter(events))

        assert final_content == "Feature"
        # Verify updates sent to Live
        assert mock_live_instance.update.call_count >= 3  # 1 initial + 3 events


def test_confirm_action(mock_ui):
    """Test confirmation dialog."""
    with patch("commitai.ui.core.Confirm.ask", return_value=True) as mock_ask:
        assert mock_ui.confirm_action("Do it?") is True
        mock_ask.assert_called_once()


def test_print_helpers(mock_ui):
    """Test helper print methods."""
    mock_ui.print_error("Bad")
    mock_ui.console.print.assert_called_with("[error]❌ Bad[/error]")

    mock_ui.print_success("Good")
    mock_ui.console.print.assert_called_with("[success]✅ Good[/success]")
