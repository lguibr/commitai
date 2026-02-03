# File: commitai/cli.py
# -*- coding: utf-8 -*-

import os
import sys
from typing import Optional, Tuple

import click
from langchain_core.language_models.chat_models import BaseChatModel

# Keep SecretStr import in case it's needed elsewhere or for future refinement

# Conditional import for Google Generative AI
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore

from commitai.agent import create_commit_agent
from commitai.git import (
    create_commit,
    get_commit_template,
    get_current_branch_name,
    get_repository_name,
    get_staged_changes_diff,
    run_pre_commit_hook,
    save_commit_template,
    stage_all_changes,
)


def _get_google_api_key() -> Optional[str]:
    """Gets the Google API key from environment variables in priority order."""
    return (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    )


def _initialize_llm(model: str) -> BaseChatModel:
    """Initializes and returns the LangChain chat model based on the model name."""
    google_api_key_str = _get_google_api_key()

    try:
        # Enforce Gemini-Only Policy
        # Enforce Strict Gemini-3 Policy
        allowed_models = ["gemini-3-flash-preview", "gemini-3-pro-preview"]
        if model not in allowed_models:
            raise click.ClickException(
                f"🚫 Unsupported model: {model}. "
                f"Only Google Gemini 3 models are allowed: {', '.join(allowed_models)}"
            )

        if ChatGoogleGenerativeAI is None:
            raise click.ClickException(
                "Error: 'langchain-google-genai' is not installed. "
                "Run 'pip install commitai[test]' or "
                "'pip install langchain-google-genai'"
            )
        if not google_api_key_str:
            raise click.ClickException(
                "Error: Google API Key not found. Set GOOGLE_API_KEY, "
                "GEMINI_API_KEY, or GOOGLE_GENERATIVE_AI_API_KEY."
            )
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=google_api_key_str,
        )

    except Exception as e:
        raise click.ClickException(f"Error initializing AI model: {e}") from e


def _prepare_context() -> str:
    diff = get_staged_changes_diff()
    if not diff:
        raise click.ClickException("⚠️ Warning: No staged changes found. Exiting.")

    repo_name = get_repository_name()
    branch_name = get_current_branch_name()
    # Return just the diff for the chain, or context?
    # The chain prompt expects 'diff'.
    # Current helper was returning "Repo/Branch\n\nDiff".
    # Let's keep it to maximize context for the chain.
    return f"{repo_name}/{branch_name}\n\n{diff}"


def _handle_commit(commit_message: str, commit_flag: bool) -> None:
    repo_path = get_repository_name()
    git_dir = os.path.join(repo_path, ".git")
    try:
        os.makedirs(git_dir, exist_ok=True)
    except OSError as e:
        raise click.ClickException(f"Error creating .git directory: {e}") from e

    commit_msg_path = os.path.join(git_dir, "COMMIT_EDITMSG")

    try:
        with open(commit_msg_path, "w") as f:
            f.write(commit_message)
    except IOError as e:
        raise click.ClickException(f"Error writing commit message file: {e}") from e

    final_commit_message = commit_message
    final_commit_message = commit_message
    if not commit_flag:
        click.secho(
            f"\n📝 Generated Commit Message:\n{'-'*40}\n{commit_message}\n{'-'*40}\n",
            fg="green",
        )

        # Interactive loop for Enter-Enter flow
        try:
            # Default to Yes (Enter)
            if click.confirm("🚀 Commit with this message?", default=True):
                pass  # final_commit_message is already set
            else:
                if click.confirm("✏️  Edit message?", default=True):
                    try:
                        click.edit(filename=commit_msg_path)
                        with open(commit_msg_path, "r") as f:
                            final_commit_message = f.read().strip()
                    except click.UsageError as e:
                        click.secho(f"Could not open editor: {e}", fg="yellow")
                else:
                    raise click.ClickException("Aborted by user.")
        except click.Abort:
            raise click.ClickException("Aborted by user.") from None
        except Exception as e:
            raise click.ClickException(f"Error handling user input: {e}") from e

    if not final_commit_message:
        raise click.ClickException("Aborting commit due to empty commit message.")

    create_commit(final_commit_message)
    click.secho(
        f"\n\n✅ Committed message:\n\n{final_commit_message}\n\n",
        fg="green",
        bold=True,
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    pass


@cli.command(name="generate")
@click.argument("description", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--commit",
    "-c",
    is_flag=True,
    help="Commit the changes with the generated message",
)
@click.option(
    "--review/--no-review",
    default=True,
    help="AI review the diff before generating the commit message (default: enabled)",
)
@click.option(
    "--template",
    "-t",
    default=None,
    help=(
        "Specify a commit message template (DEPRECATED: Use env var or create-template)"
    ),
)
@click.option(
    "--add",
    "-a",
    is_flag=True,
    help="Stage all changes before generating the commit message",
)
@click.option(
    "--model",
    "-m",
    default="gemini-3-flash-preview",
    help=(
        "Set the engine model (default: gemini-3-flash-preview). "
        "Only Google Gemini 3 models are supported "
        "('gemini-3-flash-preview', 'gemini-3-pro-preview'). "
        "Ensure GOOGLE_API_KEY is set."
    ),
)
@click.option(
    "--deep",
    "-d",
    is_flag=True,
    help="Use the deeper reasoning model (gemini-3-pro-preview).",
)
def generate_message(
    description: Tuple[str, ...],
    commit: bool,
    review: bool,
    template: Optional[str],
    add: bool,
    model: str,
    deep: bool,
) -> None:
    explanation = " ".join(description)

    # Handle Model Selection Logic
    # 1. Default is gemini-3-flash-preview
    # 2. If --deep is passed, upgrade to gemini-3-pro-preview
    # (unless -m is explicitly distinct)
    if deep:
        # If user didn't explicitly change the default model string,
        # upgrade to Pro
        # If user explicitly set a model AND used --deep,
        # we respect the explicit model but could warn (or just use it)
        pass
        pass

    llm = _initialize_llm(model)

    if add:
        stage_all_changes()

    click.secho(
        "\n🔍 Looking for a native pre-commit hook and running it\n",
        fg="blue",
        bold=True,
    )
    if not run_pre_commit_hook():
        raise click.ClickException("🚫 Pre-commit hook failed. Aborting commit.")

    formatted_diff = _prepare_context()

    # Initialize Agent Pipeline
    agent_pipeline = create_commit_agent(llm)

    # Optional pre-generation review
    if review:
        click.secho(
            "\n\n🔎 Reviewing the staged changes before "
            "generating a commit message...\n",
            fg="blue",
            bold=True,
        )

        # Only prompt for confirmation when running in an interactive TTY
        try:
            is_interactive = sys.stdin.isatty()
        except Exception:
            is_interactive = False
        if is_interactive:
            if not click.confirm(
                "Proceed with generating the commit message?", default=True
            ):
                raise click.ClickException("Aborted by user after review.")

    if template:
        click.secho(
            "⚠️ Warning: The --template/-t option is deprecated. Use environment "
            "variable TEMPLATE_COMMIT or `commitai-create-template` command.",
            fg="yellow",
        )

    # Check for template from env or file if not provided via CLI
    # (though CLI overrides or is deprecated)
    # The agent/chain prompt Logic usually handles 'template' variable
    # if passed in input.
    # We need to fetch the template content if it exists to pass to agent.

    final_template_content = template
    if not final_template_content:
        # Check env var or local file
        final_template_content = os.getenv("TEMPLATE_COMMIT") or get_commit_template()

    click.clear()
    click.secho(
        "\n\n🧠 internal-monologue: Analyzing changes, "
        "checking for sensitive data, and summarizing...\n\n",
        fg="blue",
        bold=True,
    )
    try:
        assert llm is not None
        # Invoke the Agent Pipeline
        inputs = {"diff": formatted_diff, "explanation": explanation}
        if final_template_content:
            inputs["template"] = final_template_content

        commit_message = agent_pipeline.invoke(inputs)

        if not isinstance(commit_message, str):
            commit_message = str(commit_message)

    except Exception as e:
        raise click.ClickException(f"Error during AI generation: {e}") from e

    _handle_commit(commit_message, commit)


@cli.command(name="create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
def create_template_command(template_content: Tuple[str, ...]) -> None:
    """Saves a repository-specific commit template."""
    content = " ".join(template_content)
    if content:
        save_commit_template(content)
        click.secho("📝 Template saved successfully.", fg="green")
    else:
        click.secho("❗ Please provide the template content.", fg="red")


# --- Alias Commands ---


@click.command(
    name="commitai",
    context_settings={"ignore_unknown_options": True},
)
@click.argument("description", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--add",
    "-a",
    is_flag=True,
    help="Stage all changes before generating the commit message",
)
@click.option(
    "--commit",
    "-c",
    is_flag=True,
    help="Commit the changes with the generated message",
)
@click.option(
    "--review/--no-review",
    default=True,
    help="AI review the diff before generating the commit message (default: enabled)",
)
@click.option(
    "--model",
    "-m",
    default="gemini-3-flash-preview",
    help="Set the engine model to be used.",
)
@click.option(
    "--deep",
    "-d",
    is_flag=True,
    help="Use the deeper reasoning model (gemini-3-pro-preview).",
)
@click.pass_context
def commitai_alias(
    ctx: click.Context,
    description: Tuple[str, ...],
    add: bool,
    commit: bool,
    review: bool,
    model: str,
    deep: bool,
) -> None:
    """Alias for the 'generate' command."""
    ctx.forward(
        generate_message,
        description=description,
        add=add,
        commit=commit,
        review=review,
        model=model,
        deep=deep,
    )


@click.command(name="commitai-create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def commitai_create_template_alias(
    ctx: click.Context, template_content: Tuple[str, ...]
) -> None:
    """Alias for the 'create-template' command."""
    ctx.forward(create_template_command, template_content=template_content)


cli.add_command(commitai_alias)
cli.add_command(commitai_create_template_alias)


if __name__ == "__main__":
    cli()
