from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

from commitai.agent.pr_agent import create_pr_agent


def test_create_pr_agent():
    llm_mock = MagicMock()
    agent = create_pr_agent(llm_mock)
    assert isinstance(agent, Runnable)


def test_run_pr_agent():
    # Test the bridge
    llm_mock = MagicMock()

    # We won't run the actual agent stream here because it uses an LLM,
    # but we can mock create_react_agent
    with patch("commitai.agent.pr_agent.create_react_agent") as mock_cra:
        mock_compiled = MagicMock()
        mock_cra.return_value = mock_compiled

        mock_compiled.stream.return_value = [
            {"agent": {"messages": [AIMessage(content="chunk 1")]}},
            {"agent": {"messages": [AIMessage(content="chunk 2")]}},
        ]

        test_agent = create_pr_agent(llm_mock)
        assert isinstance(test_agent, Runnable)
