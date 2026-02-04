import asyncio
import queue
import subprocess
import threading
import time
from typing import Any, Dict, Generator, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import tool

# Standard LangGraph ReAct imports
from langgraph.prebuilt import create_react_agent

# --- HELPER FUNCTIONS (Former Custom Middleware Logic) ---


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


# --- AGENT FACTORY ---


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


def _run_async_bridge(
    q_ref: queue.SimpleQueue[Any],
    agent_graph: Any,
    messages: List[Any],
) -> None:
    """Helper to run the async event stream in a separate thread."""

    async def consume_stream() -> None:
        try:
            # We must use 'v2' events to get token streaming
            async for event in agent_graph.astream_events(
                {"messages": messages}, version="v2"
            ):
                q_ref.put(event)
        except Exception as e:
            q_ref.put({"type": "error", "error": e})
        finally:
            q_ref.put(None)  # Sentinel to stop

    asyncio.run(consume_stream())


def create_commit_agent(llm: BaseChatModel) -> Runnable:
    # 1. Configure System Prompt
    # We use a template, but create_agent expects a static string or message.
    # OR we can format it before passing to invoke.
    # Since create_agent uses a compiled graph, we can pass 'messages' in input.
    # We'll construct the system prompt dynamically in the execution wrapper.

    first_line_prompt = (
        "You are CommitAI, a State-of-the-Art autonomous commiting agent."
    )
    prompt_lines = [
        first_line_prompt,
        "Your purpose is to craft the PERFECT Conventional Commit message.",
        "You are NOT a summarizer. You are a deep-context analyst.",
        "You DO NOT guess. You VERIFY.",
        "",
        "CONTEXT:",
        "- User Explanation: {explanation}",
        "- Detected TODOs: {todo_str}",
        "- Auto-Summary: {summary}",
        "- Staged Diff: {diff}",
        "",
        "YOUR AVAILABLE TOOLS (USE AGGRESSIVELY):",
        "- `shell`: EXECUTE 'git log -n 5' or 'git diff HEAD~1' for context.",
        "",
        "THE PROTOCOL OF EXCELLENCE:",
        "1. ANALYZE 'why' it changed, not just 'what'.",
        "2. CHECK patters. Is this a refactor? Use `git log`.",
        "3. SECURITY. If you see secrets, HALT and WARN.",
        "4. SYNTHESIZE a Conventional Commit message (feat, fix, refactor, etc).",
        "",
        "FINAL OUTPUT:",
        "Your final answer MUST be ONLY the commit message.",
        "Make it beautiful. Make it true. Make it eternal.",
    ]
    base_system_template = "\n".join(prompt_lines)

    # 2. Create ReAct Agent (Standard Graph)
    # This automatically handles the Action -> Observation -> Thought lookback loop.
    agent_graph = create_react_agent(
        model=llm,
        tools=[shell],
        # System prompt injected via state_modifier or checkpointer if needed.
        # For simplicity in create_react_agent, we prepend it to messages in execution.
    )

    # 4. Streaming Wrapper
    def run_pipeline(inputs: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Executes the agent pipeline with pre-processing and streaming.
        """
        # Pre-processing
        yield {"type": "thought", "content": "Processing context..."}
        diff = inputs.get("diff", "")

        # 1. Scan/Summarize (Synchronous)
        todo_data = scan_todos(diff)
        summary = summarize_context(llm, diff)

        # 2. Format Context
        formatted_prompt = base_system_template.format(
            explanation=inputs.get("explanation", "None"),
            todo_str=todo_data["todo_str"],
            summary=summary,
            diff=diff,
        )

        # 3. Prepare Input State
        # The agent graph expects 'messages'.
        messages = [
            SystemMessage(content=formatted_prompt),
            HumanMessage(content="Generate the commit message."),
        ]

        # 4. Stream Execution (V2 Standard via Threaded Async Bridge)
        # Robust pattern: Run async loop in a separate thread, push to queue.

        try:
            yield {"type": "thought", "content": "Initializing streaming..."}

            # Queue for events
            q: queue.SimpleQueue[Any] = queue.SimpleQueue()

            # Start thread
            t = threading.Thread(
                target=_run_async_bridge, args=(q, agent_graph, messages)
            )
            t.start()

            # Consume from queue locally (Sync)
            while True:
                item = q.get()
                if item is None:
                    break

                if isinstance(item, dict) and "error" in item:
                    yield {"type": "error", "content": f"Stream Error: {item['error']}"}
                    continue

                event = item
                kind = event["event"]
                data = event["data"]

                # 1. Output Tokens (Final Message or Thoughts)
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk:
                        content = chunk.content
                        # Handle complex content (list of dicts from Gemini)
                        if isinstance(content, list):
                            text_content = ""
                            for part in content:
                                if (
                                    isinstance(part, dict)
                                    and part.get("type") == "text"
                                ):
                                    text_content += part.get("text", "")
                            content = text_content

                        if content:
                            yield {"type": "token", "content": content}

                # 2. Tool Start
                elif kind == "on_tool_start":
                    name = event["name"]
                    inputs = data.get("input")
                    content_str = (
                        f"[bold cyan]🛠️  Tool Call:[/bold cyan] {name}\n"
                        f"    [dim]Args: {inputs}[/dim]"
                    )
                    yield {"type": "tool_use", "content": content_str}
                    time.sleep(0.05)

                # 3. Tool Output
                elif kind == "on_tool_end":
                    name = event["name"]
                    output = data.get("output")

                    output_str = str(output)
                    if len(output_str) > 500:
                        output_str = output_str[:500] + "... (truncated)"

                    content_str = (
                        f"[bold green]✅  Output ({name}):[/bold green]\n"
                        f"    [dim]{output_str}[/dim]"
                    )
                    yield {"type": "tool_output", "content": content_str}
                    time.sleep(0.05)

            t.join()

        except Exception as e:
            yield {"type": "error", "content": f"Agent Error: {str(e)}"}

    # Return the runnable wrapper
    return RunnableLambda(run_pipeline)
