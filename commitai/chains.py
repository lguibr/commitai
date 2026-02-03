from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough


class CommitState(TypedDict):
    diff: str
    explanation: Optional[str]
    summary: Optional[str]
    todos: Optional[List[str]]


class SummarizationMiddleware:
    """Middleware to summarize the diff before generating the commit message."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_template(
            "Summarize the following code changes concisely in 1-2 sentences:\n\n{diff}"
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def __call__(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the summarizer and add 'summary' to the state."""
        diff = inputs.get("diff", "")
        if not diff:
            return {**inputs, "summary": ""}

        # We invoke the chain synchronously here
        summary = self.chain.invoke({"diff": diff})
        return {**inputs, "summary": summary}


class TodoMiddleware:
    """Middleware to scan the diff for TODO/FIXME/HACK comments."""

    def __call__(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        diff = inputs.get("diff", "")
        todos = []
        for line in diff.splitlines():
            if line.startswith("+"):
                lower_line = line.lower()
                if (
                    "todo" in lower_line
                    or "fixme" in lower_line
                    or "hack" in lower_line
                ):
                    # Strip the + and whitespace
                    clean_line = line[1:].strip()
                    todos.append(clean_line)

        return {**inputs, "todos": todos}


def create_commit_chain(llm: BaseChatModel) -> Runnable:
    """Creates the full commit generation pipeline with middleware."""

    # 1. Initialize Middlewares
    summarizer = SummarizationMiddleware(llm)
    todo_scanner = TodoMiddleware()

    # 2. Define the Prompt
    # We include placeholders for summary and todos if they exist
    system_template = (
        "You are an expert software engineer and git commit message generator.\n"
        "Your task is to generate a clean, concise commit message following the "
        "Conventional Commits specification.\n\n"
        "Values from middleware:\n"
        "{summary_section}\n"
        "{todo_section}\n\n"
        "Input context:\n"
        "{explanation_section}\n\n"
        "Existing Code Changes (Diff):\n"
        "{diff}\n\n"
        "Instructions:\n"
        "1. Use the format: <type>(<scope>): <subject>\n"
        "2. Keep the subject line under 50 characters if possible.\n"
        "3. If there are multiple changes, provide a bulleted body.\n"
        "4. If TODOs were detected, mention them in the footer or body as "
        "appropriate.\n"
        "5. If an explanation is provided, prioritize it.\n"
    )
    prompt = ChatPromptTemplate.from_template(system_template)

    # 3. Helper to format the prompt inputs from state
    def format_inputs(state: CommitState) -> Dict[str, Any]:
        summary = state.get("summary")
        todos = state.get("todos")
        explanation = state.get("explanation")

        summary_section = f"Summary of changes:\n{summary}\n" if summary else ""

        todo_section = ""
        if todos:
            todo_section = (
                "Detected TODOs in this diff:\n"
                + "\n".join(f"- {t}" for t in todos)
                + "\n"
            )

        explanation_section = ""
        if explanation:
            explanation_section = f"User Explanation:\n{explanation}\n"

        return {
            "diff": state["diff"],
            "summary_section": summary_section,
            "todo_section": todo_section,
            "explanation_section": explanation_section,
        }

    # 4. Construct the Pipeline
    # Parallel step to run middlewares
    # (conceptually, though here we chain them or use RunnablePassthrough)
    # Since middlewares modify state, we can chain them:

    middleware_chain: Runnable = (
        RunnablePassthrough()
        | RunnableLambda(todo_scanner)
        | RunnableLambda(summarizer)
    )

    # Final generation chain
    generation_chain = (
        middleware_chain
        | RunnableLambda(format_inputs)
        | prompt
        | llm
        | StrOutputParser()
    )

    return generation_chain
