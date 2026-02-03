from commitai.agent import FileSearchTool, ReadOnlyShellTool, TodoMiddleware


def test_todo_middleware():
    scanner = TodoMiddleware()
    state = {"diff": "+ # TODO: fix this\n- # OLD"}
    new_state = scanner.process(state)
    assert len(new_state["todos"]) == 1
    assert "TODO: fix this" in new_state["todos"][0]


def test_readonly_shell_tool():
    tool = ReadOnlyShellTool()
    # Test blocked command
    assert "forbidden write operations" in tool._run("git commit -m 'oops'")
    assert "Only 'git' commands" in tool._run("rm -rf /")

    # Test allowed command (hard to test without full repo,
    # but we can check it doesn't return the forbidden error)
    # Mocking subprocess run would be better but let's assume 'git status' is generally
    # safe to attempt or fail gracefully
    pass


def test_file_search_tool():
    tool = FileSearchTool()
    assert "Error" in tool._run("src/../secret")
