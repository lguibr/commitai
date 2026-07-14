from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from commitai.agent.core import create_commit_agent
from commitai.agent.tools import scan_todos, summarize_context


def test_agent_v3_initialization():
    """Verify that the V3 agent utilizes create_react_agent."""
    mock_llm = MagicMock()

    with patch("commitai.agent.core.create_react_agent") as mock_create_react:
        mock_create_react.return_value = MagicMock()

        agent_runnable = create_commit_agent(mock_llm)

        # Verify create_react_agent was called with correct model and tools
        mock_create_react.assert_called_once()
        _, kwargs = mock_create_react.call_args
        assert kwargs["model"] == mock_llm
        assert "tools" in kwargs
        # Ensure 'shell' tool is in the list
        tools = kwargs["tools"]
        assert len(tools) > 0
        assert tools[0].name == "shell"

        assert agent_runnable is not None


def test_scan_todos():
    """Test TODO scanning logic."""
    diff_with_todo = "+ # TODO: Fix this later\n+ function foo() {\n+ # FIXME: Old bug"
    result = scan_todos(diff_with_todo)

    assert "todos" in result
    assert "todo_str" in result
    assert len(result["todos"]) == 2
    assert "Fix this later" in result["todos"][0]
    assert "Old bug" in result["todos"][1]
    assert "- # TODO: Fix this later" in result["todo_str"]


def test_scan_todos_none():
    """Test TODO scanning with no todos."""
    diff_clean = "+ function foo() {}"
    result = scan_todos(diff_clean)
    assert not result["todos"]
    assert result["todo_str"] == "None"


def test_summarize_context_short():
    """Test summarization (even short diffs trigger LLM now)."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Summary")
    diff = "short diff"
    summary = summarize_context(mock_llm, diff)
    assert summary == "Summary"


def test_run_pipeline_streaming():
    """Test the streaming pipeline execution."""
    mock_llm = MagicMock()

    # We mock threading.Thread to inject events into the queue that the pipeline creates
    with (
        patch("commitai.agent.core.threading.Thread") as mock_thread,
        patch("commitai.agent.core.scan_todos"),
        patch("commitai.agent.core.summarize_context"),
        patch("commitai.agent.core.create_react_agent") as mock_cra,
    ):
        mock_graph = MagicMock()
        mock_cra.return_value = mock_graph

        # When t.start() is called, we populate the queue found in t.args
        def side_effect_start():
            # args=(q, agent_graph, messages)
            # We get the 'q' instance from the constructor call args of Thread
            # mock_thread_cls.call_args gives us the arguments passed to Thread(...)
            _, thread_kwargs = mock_thread.call_args
            # Or args might be positional? In agent.py: target=..., args=(...)
            thread_args = thread_kwargs.get("args")
            q = thread_args[0]

            # Simulate events
            # 1. Tool Call
            q.put(
                {
                    "event": "on_tool_start",
                    "name": "shell",
                    "data": {"input": {"command": "git log"}},
                }
            )
            # 2. Tool Output
            tool_msg = ToolMessage(content="commit info", tool_call_id="1")
            q.put(
                {"event": "on_tool_end", "name": "shell", "data": {"output": tool_msg}}
            )
            # 3. Token Stream (Gemini style list)
            q.put(
                {
                    "event": "on_chat_model_stream",
                    "data": {
                        "chunk": AIMessage(content=[{"type": "text", "text": "feat: "}])
                    },
                }
            )
            q.put(
                {
                    "event": "on_chat_model_stream",
                    "data": {
                        "chunk": AIMessage(
                            content=[{"type": "text", "text": "streaming"}]
                        )
                    },
                }
            )
            # 4. Stop
            q.put(None)

        # Setup the mock thread instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        mock_thread_instance.start.side_effect = side_effect_start

        # Initialize agent
        pipeline_func = create_commit_agent(mock_llm)
        inputs = {"diff": "some diff", "explanation": "expl"}

        # Invoke stream via RunnableLambda
        stream_gen = pipeline_func.stream(inputs)
        results = list(stream_gen)

        # Check Results
        # Thought events
        assert any(r["type"] == "thought" for r in results)

        # Tool Use
        tool_uses = [r for r in results if r["type"] == "tool_use"]
        assert len(tool_uses) == 1
        assert "git log" in tool_uses[0]["content"]

        # Tool Output
        tool_outputs = [r for r in results if r["type"] == "tool_output"]
        assert len(tool_outputs) == 1
        # The output logic wraps it in [bold green]...
        assert "commit info" in tool_outputs[0]["content"]

        # Tokens
        tokens = [r["content"] for r in results if r["type"] == "token"]
        full_text = "".join(tokens)
        assert "feat: streaming" in full_text
