import asyncio
import queue
import threading
import time
from typing import Any, Dict, Generator, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langgraph.prebuilt import create_react_agent

from .tools import scan_todos, shell, summarize_context


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


def create_commit_agent(llm: BaseChatModel) -> Runnable:  # noqa: C901
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

    agent_graph = create_react_agent(
        model=llm,
        tools=[shell],
    )

    def run_pipeline(inputs: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        yield {"type": "thought", "content": "Processing context..."}
        diff = inputs.get("diff", "")

        todo_data = scan_todos(diff)
        summary = summarize_context(llm, diff)

        formatted_prompt = base_system_template.format(
            explanation=inputs.get("explanation", "None"),
            todo_str=todo_data["todo_str"],
            summary=summary,
            diff=diff,
        )

        messages = [
            SystemMessage(content=formatted_prompt),
            HumanMessage(content="Generate the commit message."),
        ]

        try:
            yield {"type": "thought", "content": "Initializing streaming..."}

            q: queue.SimpleQueue[Any] = queue.SimpleQueue()

            t = threading.Thread(
                target=_run_async_bridge, args=(q, agent_graph, messages)
            )
            t.start()

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

                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk:
                        content = chunk.content
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

                elif kind == "on_tool_start":
                    name = event["name"]
                    inputs_data = data.get("input")
                    content_str = (
                        f"[bold cyan]🛠️  Tool Call:[/bold cyan] {name}\n"
                        f"    [dim]Args: {inputs_data}[/dim]"
                    )
                    yield {"type": "tool_use", "content": content_str}
                    time.sleep(0.05)

                elif kind == "on_tool_end":
                    name = event["name"]
                    output = data.get("output")

                    if hasattr(output, "content"):
                        output_str = str(output.content)
                    else:
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

    return RunnableLambda(run_pipeline)
