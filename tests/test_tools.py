import subprocess
from unittest.mock import MagicMock, patch

from commitai.agent.tools import scan_todos, shell, summarize_context


def test_scan_todos():
    diff = "some code\n+ # TODO: fix this\n- # fixme old\n+ code # FIXME: bad"
    res = scan_todos(diff)
    assert len(res["todos"]) == 2
    assert "fix this" in res["todo_str"]


def test_summarize_context():
    llm = MagicMock()
    llm.invoke.return_value.content = "Summary"
    res = summarize_context(llm, "diff")
    assert res == "Summary"


def test_summarize_context_empty():
    llm = MagicMock()
    res = summarize_context(llm, "")
    assert res == "None"


def test_summarize_context_error():
    llm = MagicMock()
    llm.invoke.side_effect = Exception("error")
    res = summarize_context(llm, "diff")
    assert res == "Summary unavailable"


def test_shell_not_git():
    res = shell.invoke("ls -la")
    assert "Only git commands" in res


def test_shell_not_allowed():
    res = shell.invoke("git fake")
    assert "not in the whitelist" in res


def test_shell_destructive():
    res = shell.invoke("git log && git commit -m msg")
    assert "is forbidden" in res


@patch("commitai.agent.tools.subprocess.check_output")
def test_shell_success(mock_check):
    mock_check.return_value = b"git output"
    res = shell.invoke("git log")
    assert res == "git output"


@patch("commitai.agent.tools.subprocess.check_output")
def test_shell_error(mock_check):
    mock_check.side_effect = subprocess.CalledProcessError(1, "git log", b"error")
    res = shell.invoke("git log")
    assert "error" in res
