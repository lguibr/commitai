from unittest.mock import MagicMock, patch

from commitai.agent import create_commit_agent


def test_agent_v3_initialization():
    """Verify that the V3 agent can be initialized with the new middlewares."""
    mock_llm = MagicMock()

    # We need to mock create_agent because it will try to set up real tools/middlewares
    # and we don't want to run them or depend on OS/Git state during this unit test.
    # However, we want to verify that create_agent CALL was correct (args passed).

    with patch("commitai.agent.create_agent") as mock_create_agent:
        mock_create_agent.return_value = MagicMock()  # Return a mock graph

        # Also mock the middlewares to check if they were instantiated
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
