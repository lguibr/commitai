import subprocess
from typing import Any, Dict

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool


def scan_todos(diff: str) -> Dict[str, Any]:
    """Scans diff for TODOs."""
    todos = []
    if diff:
        for line in diff.splitlines():
            if line.startswith("+") and any(
                x in line.lower() for x in ["todo", "fixme"]
            ):
                todos.append(line[1:].strip())

    todo_str = "\n".join(f"- {t}" for t in todos) if todos else "None"
    return {"todos": todos, "todo_str": todo_str}


def summarize_context(llm: BaseChatModel, diff: str) -> str:
    """Summarize diff context using LLM (Legacy logic preserved as pre-processing)."""
    if not diff:
        return "None"

    msg = f"Summarize these changes in 2 sentences:\n\n{diff[:5000]}"
    try:
        resp = llm.invoke(msg)
        return str(resp.content)
    except Exception:
        return "Summary unavailable"


@tool
def shell(command: str) -> str:
    """
    Executes a read-only git command to inspect the repository.
    Allowed commands: git log, git diff, git show, git status.
    Forbidden: git commit, git push, rm, mv, etc.
    """
    cmd = command.strip()
    if not cmd.startswith("git"):
        return "Error: Only git commands are allowed."

    # Whitelist
    allowed = ["log", "diff", "show", "status", "rev-parse", "ls-files"]
    if not any(sub in cmd for sub in allowed):
        return f"Error: Command '{cmd}' is not in the whitelist: {allowed}"

    # Block destructive
    forbidden = [
        "push",
        "commit",
        "add",
        "rm",
        "mv",
        "checkout",
        "branch",
        "merge",
        "rebase",
    ]
    if any(sub in cmd for sub in forbidden):
        return f"Error: Destructive command '{cmd}' is forbidden."

    try:
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return result.decode("utf-8")
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.output.decode('utf-8')}"
    except Exception as e:
        return f"Error: {str(e)}"
