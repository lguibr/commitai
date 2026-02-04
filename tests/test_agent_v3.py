from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from commitai.agent import create_commit_agent, scan_todos, summarize_context


def test_agent_v3_initialization():
    """Verify that the V3 agent can be initialized with the new middlewares."""
    mock_llm = MagicMock()

    with patch("commitai.agent.create_agent") as mock_create_agent:
        mock_create_agent.return_value = MagicMock()  # Return a mock graph

        with (
            patch("commitai.agent.SummarizationMiddleware") as mock_summ,
            patch("commitai.agent.FilesystemFileSearchMiddleware") as mock_files,
            patch("commitai.agent.ShellToolMiddleware") as mock_shell,
            patch("commitai.agent.HumanInTheLoopMiddleware") as mock_hitl,
            patch("commitai.agent.LLMToolSelectorMiddleware") as mock_selector,
        ):
            agent_runnable = create_commit_agent(mock_llm)

            # Verify middlewares were initialized
            mock_summ.assert_called_once()
            mock_files.assert_called_once()
            mock_shell.assert_called_once()
            mock_hitl.assert_called_once()
            mock_selector.assert_called_once()

            # Verify create_agent call
            mock_create_agent.assert_called_once()
            _, kwargs = mock_create_agent.call_args
            assert "middleware" in kwargs
            assert len(kwargs["middleware"]) == 5

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
    # Check for the raw line content as captured
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

    # It returns content directly now
    assert summary == "Summary"
    mock_llm.invoke.assert_called_once()


def test_summarize_context_long():
    """Test summarization triggered for long diffs."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Summary of changes")

    # Create diff > 3000 chars
    diff = "a" * 3005
    summary = summarize_context(mock_llm, diff)

    assert summary == "Summary of changes"
    mock_llm.invoke.assert_called_once()


def test_run_pipeline_streaming():
    """Test the streaming pipeline execution."""
    mock_llm = MagicMock()
    # Mock LLM response for summarize_context call inside pipeline
    mock_llm.invoke.return_value = AIMessage(content="Summary")

    # Mock the agent graph created inside factory
    mock_graph = MagicMock()

    # Mock stream output from graph
    final_message = AIMessage(content="feat: new feature")
    events = [
        {
            "messages": [
                AIMessage(
                    content="", tool_calls=[{"name": "git_log", "args": {}, "id": "1"}]
                )
            ]
        },
        {"messages": [final_message]},
    ]
    mock_graph.stream.return_value = iter(events)

    with patch("commitai.agent.create_agent", return_value=mock_graph):
        with (
            patch("commitai.agent.SummarizationMiddleware"),
            patch("commitai.agent.FilesystemFileSearchMiddleware"),
            patch("commitai.agent.ShellToolMiddleware"),
            patch("commitai.agent.HumanInTheLoopMiddleware"),
            patch("commitai.agent.LLMToolSelectorMiddleware"),
        ):
            pipeline_func = create_commit_agent(mock_llm)

            inputs = {"diff": "some diff", "explanation": "expl"}
            # Use stream() to ensure we get the generator/iterator properly
            stream_gen = pipeline_func.stream(inputs)

            results = list(stream_gen)

            # Verify we received dicts
            for r in results:
                assert isinstance(r, dict), f"Received non-dict result: {r}"

            # Check for thought event (from tool call)
            assert any(r["type"] == "thought" for r in results)

            # Check for token events (from final message)
            token_events = [r for r in results if r["type"] == "token"]
            assert len(token_events) > 0
            full_text = "".join(t["content"] for t in token_events)
            assert "feat: new feature" in full_text
