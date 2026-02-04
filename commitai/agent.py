import os
import time
from typing import Any, Dict, Generator, List, cast

# Import new middlewares and agent factory
from langchain.agents import create_agent
from langchain.agents.middleware import (
    FilesystemFileSearchMiddleware,
    HumanInTheLoopMiddleware,
    LLMToolSelectorMiddleware,
    ShellToolMiddleware,
    SummarizationMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda

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
        "- `file_search`: LOCATE related files to understand architecture.",
        "- `file_read`: READ surrounding code for semantic meaning.",
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

    # 2. Configure Middlewares

    # Summarization Middleware (for conversation history)
    # Trigger summarization if history exceeds token limit.
    summ_mw = SummarizationMiddleware(
        model=llm,
        trigger=("tokens", 6000),  # Adjust based on context window
        keep=("messages", 4),
    )

    # Human In The Loop
    # Require approval for shell commands to ensure safety (Read-Only enforcement)
    hitl_mw = HumanInTheLoopMiddleware(
        interrupt_on={"shell": True},
        description_prefix="⚠️ Shell command requires approval.",
    )

    # Shell Tool Middleware
    # Provides 'shell' tool.
    shell_mw = ShellToolMiddleware(
        workspace_root=os.getcwd(),
        tool_name="shell",
        tool_description=(
            "Execute git commands to inspect repository. "
            "ONLY 'git' read and not destructive commands allowed."
        ),
    )

    # File Search Middleware
    search_mw = FilesystemFileSearchMiddleware(root_path=os.getcwd(), use_ripgrep=True)

    # LLM Tool Selector
    # Helps agent pick relevant tools if we had many.
    selector_mw = LLMToolSelectorMiddleware(model=llm, max_tools=3)

    # 3. Create Agent
    # We pass empty tools list because middlewares inject them
    # or we want only middleware tools.
    agent_graph = create_agent(
        model=llm,
        tools=[],
        middleware=cast(list, [summ_mw, search_mw, shell_mw, selector_mw, hitl_mw]),
        system_prompt="You are a CommitAI Assistant. Use tools only when necessary.",
        # Fallback static prompts
    )  # type: ignore[var-annotated]

    # 4. Streaming Wrapper
    def run_pipeline(inputs: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """
        Executes the agent pipeline with pre-processing and streaming.
        """
        # Pre-processing
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

        # 4. Stream Execution
        # We use stream_mode="values" to get state updates
        try:
            # Note: If HITL interrupts, this stream might stop or yield interrupt?
            # For CLI usage, handling real interrupt/resume is complex.
            # "Human in the loop" implies we ASK the user.
            # CLI 'stream_response' doesn't support inputting approval mid-stream.
            # For now, we'll yield the interrupt as a "thought" request?

            for event in agent_graph.stream(
                {"messages": cast(List[Any], messages)}, stream_mode="values"
            ):
                last_msg = event["messages"][-1]

                # Check for Tool Calls (Thinking)
                if last_msg.type == "ai" and last_msg.tool_calls:
                    tool_names = ", ".join(t["name"] for t in last_msg.tool_calls)
                    yield {
                        "type": "thought",
                        "content": f"Deciding to use: {tool_names}...",
                    }

                # Check for Tool Outputs
                elif last_msg.type == "tool":
                    yield {
                        "type": "thought",
                        "content": f"Received output from {last_msg.name}.",
                    }

                # Check for Content (Final Answer or intermediate thought)
                elif last_msg.type == "ai" and last_msg.content:
                    # Usually the last message is the final answer if loop finishes.
                    # We store it and stream it at the end loop purely for visual effect
                    # if strictly separating.
                    # Or we can treat it as final.
                    pass

            # Final extraction (simplified)
            # Fetch final state?
            # Does stream yield the final state at the end? Yes.
            final_content = event["messages"][-1].content

            if isinstance(final_content, str) and final_content:
                yield {"type": "thought", "content": "Drafting message..."}
                # Simulate token streaming
                chunk_size = 4
                for i in range(0, len(final_content), chunk_size):
                    yield {
                        "type": "token",
                        "content": final_content[i : i + chunk_size],
                    }
                    time.sleep(0.005)

        except Exception as e:
            yield {"type": "error", "content": f"Agent Error: {str(e)}"}

    return RunnableLambda(run_pipeline)
