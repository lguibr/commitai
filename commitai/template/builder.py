def build_user_message(explanation, diff):
    return f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"


def build_review_prompt(explanation: str, formatted_diff: str) -> str:
    """Builds a review prompt asking the AI to review the diff before message
    generation.

    The review should highlight:
    - correctness concerns, risky changes, missing tests or docs
    - obvious refactors or style violations
    - a short bullet summary of the changes
    Keep it concise.
    """
    review_system = (
        "You are a senior code reviewer. "
        "You will receive a repository path/branch and a git diff. "
        "Provide a brief review focusing on potential issues, "
        "risks, and improvement suggestions. "
        "Then provide a very short summary of changes. "
        "Keep output as plain text, no markdown code fences."
    )
    if explanation:
        intro = f"High-level explanation: {explanation}\n\n{formatted_diff}"
    else:
        intro = formatted_diff
    return f"{review_system}\n\n{intro}"
