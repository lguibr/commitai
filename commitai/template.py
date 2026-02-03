# -*- coding: utf-8 -*-

# flake8: noqa: E501

default_system_message = (
    "You are a helpful git commit assistant. "
    "You will receive a git diff and generate a clear, concise, and meaningful commit message."
    "The commit message should strictly follow the conventional commit format: "
    "<type>(<scope>): <subject>\n\n<body>\n\n<footer>"
    "Types can be: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert."
    "Scope is optional and represents the section of the codebase affected by the changes."
    "Subject should be a short summary of the changes, in present tense and imperative mood."
    "Body should provide more details about the changes, if necessary."
    "Footer can contain references to issues, pull requests, or breaking changes."
    "Avoid generic messages like 'update', 'fix bugs', or 'improve code'."
    "Focus on the specific changes made and their impact."
    "Don't wrap the text in the commit message, or anything like that this text is a commit message directed sent to the user editor in commit process"
    "Don't include codeblock on the response as ``` or anything like that we need raw git message as raw txt"
)

adding_template = " The message should follow this template: "


def build_user_message(explanation, diff):
    return f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"


def build_review_prompt(explanation: str, formatted_diff: str) -> str:
    """Builds a review prompt asking the AI to review the diff before message generation.

    The review should highlight:
    - correctness concerns, risky changes, missing tests or docs
    - obvious refactors or style violations
    - a short bullet summary of the changes
    Keep it concise.
    """
    review_system = (
        "You are a senior code reviewer. You will receive a repository path/branch and a git diff. "
        "Provide a brief review focusing on potential issues, risks, and improvement suggestions. "
        "Then provide a very short summary of changes. Keep output as plain text, no markdown code fences."
    )
    if explanation:
        intro = f"High-level explanation: {explanation}\n\n{formatted_diff}"
    else:
        intro = formatted_diff
    return f"{review_system}\n\n{intro}"
