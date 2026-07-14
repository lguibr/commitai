import asyncio
import queue
import threading
import time
from typing import Any, Dict, Generator, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langgraph.prebuilt import create_react_agent

from .tools import shell


def _run_async_bridge(
    q_ref: queue.SimpleQueue[Any],
    agent_graph: Any,
    messages: List[Any],
) -> None:
    """Helper to run the async event stream in a separate thread."""

    async def consume_stream() -> None:
        try:
            async for event in agent_graph.astream_events(
                {"messages": messages}, version="v2"
            ):
                q_ref.put(event)
        except Exception as e:
            q_ref.put({"type": "error", "error": e})
        finally:
            q_ref.put(None)

    asyncio.run(consume_stream())


def create_pr_agent(llm: BaseChatModel) -> Runnable:
    first_line_prompt = (
        "You are CommitAI's PR Agent, "
        "designed to create world-class Pull Request descriptions."
    )
    prompt_lines = [
        first_line_prompt,
        "Your purpose is to craft a comprehensive, highly readable PR description "
        "based on the provided context.",
        "You are NOT a simple summarizer. "
        "You highlight key architectural changes, risks, and business value.",
        "You DO NOT guess. You VERIFY using your tools if needed.",
        "",
        "CONTEXT:",
        "- Developer Feedback: {feedback}",
        "- Target Branch: {branch}",
        "- Diff / Commits Summary: {diff}",
        "- PR Template: {template}",
        "",
        "YOUR AVAILABLE TOOLS:",
        "You are equipped with tools to view file contents ('cat <file>') ",
        "or 'git diff {branch}...HEAD' to inspect changes deeper "
        "if the initial summary is insufficient.",
        "",
        "THE PROTOCOL OF EXCELLENCE:",
        "1. Start by understanding the developer's feedback (which may be empty).",
        "2. If a PR Template is provided, you MUST structure your response "
        "to match it (fill in the sections).",
        "3. Highlight 'Why' this PR exists, not just 'What' changed.",
        "4. Include a checklist if applicable.",
        "5. Keep the formatting clean and strictly markdown.",
        "",
        "FINAL OUTPUT:",
        "Your final answer MUST be ONLY the markdown text for the PR description.",
    ]
    base_system_template = "\n".join(prompt_lines)

    agent_graph = create_react_agent(
        model=llm,
        tools=[shell],
    )

    def run_pipeline(inputs: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        yield {"type": "thought", "content": "Processing PR context..."}

        diff = inputs.get("diff", "")
        feedback = inputs.get("feedback", "None")
        branch = inputs.get("branch", "main")
        template = inputs.get("template", "None")

        formatted_prompt = base_system_template.format(
            feedback=feedback if feedback else "None",
            branch=branch,
            diff=diff,
            template=template if template else "No specific template provided.",
        )

        messages = [
            SystemMessage(content=formatted_prompt),
            HumanMessage(content="Generate the Pull Request description."),
        ]

        try:
            yield {"type": "thought", "content": "Initializing PR streaming..."}
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
                    output_str = (
                        str(output.content)
                        if hasattr(output, "content")
                        else str(output)
                    )
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
