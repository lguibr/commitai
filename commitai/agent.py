import glob
import os
import subprocess
from typing import Any, Dict, Type

# from langchain.agents import AgentExecutor, create_tool_calling_agent # Removed
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# --- TOOLS ---


class ShellInput(BaseModel):
    command: str = Field(
        description=(
            "The git command to execute (e.g., 'git status', 'git log'). "
            "Must start with 'git'."
        )
    )


class ReadOnlyShellTool(BaseTool):
    name: str = "git_shell"
    description: str = (
        "Run read-only git commands to inspect the repository state. "
        "Only 'git' commands are allowed. Write operations are blocked."
    )
    args_schema: Type[BaseModel] = ShellInput

    def _run(self, command: str) -> str:
        command = command.strip()
        if not command.startswith("git"):
            return "Error: Only 'git' commands are allowed."

        # Simple blocklist for write operations
        forbidden = [
            "push",
            "pull",
            "commit",
            "merge",
            "rebase",
            "cherry-pick",
            "stash",
            "clean",
            "reset",
            "checkout",
            "switch",
            "branch",
        ]
        if any(w in command.split() for w in forbidden):
            return f"Error: Command '{command}' contains forbidden write operations."

        try:
            # shell=True is dangerous in general, but we heavily restricted input above
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, cwd=os.getcwd()
            )
            if result.returncode != 0:
                return f"Error ({result.returncode}): {result.stderr}"
            return result.stdout
        except Exception as e:
            return f"Execution Error: {str(e)}"


class FileSearchInput(BaseModel):
    pattern: str = Field(
        description="The glob pattern to search for files (e.g., 'src/**/*.py')."
    )


class FileSearchTool(BaseTool):
    name: str = "file_search"
    description: str = (
        "Search for file paths in the project using glob patterns. "
        "Useful to find files to inspect."
    )
    args_schema: Type[BaseModel] = FileSearchInput

    def _run(self, pattern: str) -> str:
        try:
            # Security: prevent breaking out of repo?
            # For simplicity, just run glob.
            if ".." in pattern:
                return "Error: '..' not allowed in patterns."

            files = glob.glob(pattern, recursive=True)
            if not files:
                return "No files found."
            return "\n".join(files[:20])  # Limit output
        except Exception as e:
            return f"Error: {str(e)}"


class FileReadInput(BaseModel):
    file_path: str = Field(description="The path of the file to read.")


class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = "Read the contents of a specific file."
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, file_path: str) -> str:
        if ".." in file_path:
            return "Error: Traversing up directories is not allowed."
        if not os.path.exists(file_path):
            return "Error: File does not exist."
        try:
            with open(file_path, "r") as f:
                content = f.read()
                return content[:2000]  # Truncate large files
        except Exception as e:
            return f"Error reading file: {str(e)}"


# --- MIDDLEWARE (Simulated for Agent) ---


class SummarizationMiddleware:
    """Uses LLM to summarize diff before agent sees it."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        diff = inputs.get("diff", "")
        if not diff:
            return inputs

        # Simple summarization chain (inline invocation)
        # Truncate for summary
        msg = f"Summarize these changes in 2 sentences:\n\n{diff[:5000]}"
        resp = self.llm.invoke(msg)
        inputs["summary"] = resp.content
        return inputs


class TodoMiddleware:
    """Scans diff for TODOs and adds to inputs."""

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        diff = inputs.get("diff", "")
        todos = []
        for line in diff.splitlines():
            if line.startswith("+") and any(
                x in line.lower() for x in ["todo", "fixme"]
            ):
                todos.append(line[1:].strip())
        inputs["todos"] = todos
        inputs["todo_str"] = "\n".join(f"- {t}" for t in todos) if todos else "None"
        return inputs


# --- AGENT ---


# --- AGENT ---


def create_commit_agent(llm: BaseChatModel) -> Runnable:
    # 1. Init Tools
    tools = [ReadOnlyShellTool(), FileSearchTool(), FileReadTool()]

    # 2. Middlewares
    summ_mw = SummarizationMiddleware(llm)
    todo_mw = TodoMiddleware()

    # 3. Prompt
    system_prompt = """You are an expert software engineer acting as a Commit Assistant.
Your goal is to generate a conventional commit message.

Context:
- User Explanation: {explanation}
- Detected TODOs: {todo_str}
- Auto-Summary: {summary}
- Staged Diff: {diff}

You have access to tools to explore the codebase if the diff + explanation is ambiguous.
- Use `git_shell` to check status or logs.
- Use `file_search` and `file_read` to understand context of modified files.

Protocol:
1. Analyze the input.
2. If detecting POTENTIAL SENSITIVE DATA (API keys, secrets) in the diff, you MUST stop
   and ask the user (simulated by returning a warning message).
3. If clarification is needed, explore files.
4. Final Answer MUST be ONLY the commit message.
"""
    # Note: create_react_agent handles the prompt internally or via state_modifier.
    # We can pass a system string or a function. Since our prompt depends on dynamic
    # variables (diff, explanation, etc.), we need to inject them. LangGraph's
    # prebuilt agent usually takes a static system message. However, we can use the
    # 'messages' state. But to keep it simple and compatible with existing 'invoke'
    # interface: We will format the system prompt in the wrapper and pass it as the
    # first message.

    # Actually, create_react_agent supports 'state_modifier'.
    # If we pass a formatted string, it works as system prompt.

    # 4. Construct Graph
    # We don't construct the graph with ALL variables pre-bound if they change per run.
    # Instead, we'll format the prompt in the pipeline and pass it to the agent.

    agent_graph = create_react_agent(llm, tools)

    # 5. Pipeline with Middleware
    def run_pipeline(inputs: Dict[str, Any]) -> str:
        # Run Middleware
        state = inputs.copy()
        state = todo_mw.process(state)
        state = summ_mw.process(state)

        # Inject formatted fields if missing
        state.setdefault("explanation", "None")
        state.setdefault("summary", "None")
        state.setdefault("todo_str", "None")

        # Format System Prompt
        formatted_system_prompt = system_prompt.format(
            explanation=state["explanation"],
            todo_str=state["todo_str"],
            summary=state["summary"],
            diff=state.get("diff", ""),
        )

        # Run Agent
        # LangGraph inputs: {"messages": [{"role": "user", "content": ...}]}
        # We inject the system prompt as a SystemMessage or just update the state.
        # create_react_agent primarily looks at 'messages'.

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=formatted_system_prompt),
            HumanMessage(content="Generate the commit message."),
        ]

        # Invoke graph
        # result is a dict with 'messages'
        result = agent_graph.invoke({"messages": messages})

        # Extract last message content
        last_message = result["messages"][-1]
        return str(last_message.content)

    # Wrap in RunnableLambda to expose 'invoke'
    from langchain_core.runnables import RunnableLambda

    return RunnableLambda(run_pipeline)
