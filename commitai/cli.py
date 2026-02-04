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
    from commitai.ui import RichUI

    ui = RichUI()

    repo_path = get_repository_name()
    git_dir = os.path.join(repo_path, ".git")
    try:
        os.makedirs(git_dir, exist_ok=True)
    except OSError as e:
        ui.print_error(f"Error creating .git directory: {e}")
        sys.exit(1)

    commit_msg_path = os.path.join(git_dir, "COMMIT_EDITMSG")

    try:
        with open(commit_msg_path, "w") as f:
            f.write(commit_message)
    except IOError as e:
        ui.print_error(f"Error writing commit message file: {e}")
        sys.exit(1)

    final_commit_message = commit_message
    if not commit_flag:
        # Interactive loop handled by stream logic?
        # Actually the panel already shows it.
        # But we need to ask validation.

        # Interactive loop for Enter-Enter flow
        try:
            # Default to Yes (Enter)
            if ui.confirm_action("Commit with this message?"):
                pass  # final_commit_message is already set
            else:
                if ui.confirm_action("Edit message manually?"):
                    try:
                        click.edit(filename=commit_msg_path)
                        with open(commit_msg_path, "r") as f:
                            final_commit_message = f.read().strip()
                    except click.UsageError as e:
                        ui.print_error(f"Could not open editor: {e}")
                else:
                    ui.print_error("Aborted by user.")
                    sys.exit(0)
        except Exception as e:
            ui.print_error(f"Error handling user input: {e}")
            sys.exit(1)

    if not final_commit_message:
        ui.print_error("Aborting commit due to empty commit message.")
        sys.exit(1)

    create_commit(final_commit_message)
    ui.print_success("Committed successfully!")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    pass


@cli.command(name="generate")
@click.argument("description", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--commit",
    "-c",
    is_flag=True,
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
def generate_message(  # noqa: C901
    description: Tuple[str, ...],
    commit: bool,
    review: bool,
    template: Optional[str],
    add: bool,
    model: str,
    deep: bool = False,
) -> None:
    # Initialize Rich UI
    from commitai.ui import RichUI

    ui = RichUI()
    ui.render_header()

    explanation = " ".join(description)

    # Handle Model Selection Logic
    if deep:
        if model == "gemini-3-flash-preview":
            model = "gemini-3-pro-preview"

    llm = _initialize_llm(model)

    # Interactive Wizard Mode (if not explicitly adding all)
    if not add:
        staged = ui.interactive_staging()
        if staged:
            # Files were staged, so we should proceed with checks
            pass
    elif add:
        stage_all_changes()

    ui.console.print("\n[blue]🔍 Looking for pre-commit hook...[/blue]")
    if not run_pre_commit_hook():
        ui.print_error("Pre-commit hook failed. Aborting commit.")
        sys.exit(1)

    try:
        formatted_diff = _prepare_context()
    except click.ClickException as e:
        ui.print_error(str(e))
        sys.exit(1)

    # Initialize Agent Pipeline
    agent_pipeline = create_commit_agent(llm)

    # Optional pre-generation review
    if review:
        ui.console.print("\n[info]🔎 Reviewing staged changes...[/info]")
        # Only prompt for confirmation when running in an interactive TTY
        try:
            is_interactive = sys.stdin.isatty()
        except Exception:
            is_interactive = False
        if is_interactive:
            if not ui.confirm_action("Proceed with generation?"):
                ui.print_error("Aborted by user.")
                sys.exit(0)

    if template:
        ui.console.print("[warning]⚠️ --template/-t is deprecated.[/warning]")

    final_template_content = template
    if not final_template_content:
        final_template_content = os.getenv("TEMPLATE_COMMIT") or get_commit_template()

    # Streaming Execution
    try:
        assert llm is not None
        inputs = {"diff": formatted_diff, "explanation": explanation}
        if final_template_content:
            inputs["template"] = final_template_content

        # Invoke the Agent Pipeline (which now returns a generator)
        stream_gen = agent_pipeline.invoke(inputs)

        # Use UI to handle streaming visualization
        commit_message = ui.stream_response(stream_gen)

    except Exception as e:
        ui.print_error(f"Error during AI generation: {e}")
        sys.exit(1)

    _handle_commit(commit_message, commit)


@cli.command(name="create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
def create_template_command(template_content: Tuple[str, ...]) -> None:
    """Saves a repository-specific commit template."""
    from commitai.ui import RichUI

    ui = RichUI()

    content = " ".join(template_content)
    if content:
        save_commit_template(content)
        ui.print_success("Template saved successfully.")
    else:
        ui.print_error("Please provide the template content.")


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
