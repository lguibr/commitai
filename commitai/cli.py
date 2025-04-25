# File: commitai/cli.py
# -*- coding: utf-8 -*-

import os
from typing import Optional, Tuple

import click
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

# Keep SecretStr import in case it's needed elsewhere or for future refinement

# Conditional import for Google Generative AI
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore

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
from commitai.template import (
    adding_template,
    build_user_message,
    default_system_message,
)


# Helper function to get API key with priority
def _get_google_api_key() -> Optional[str]:
    """Gets the Google API key from environment variables in priority order."""
    return (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    )


# Helper function to initialize the LLM
def _initialize_llm(model: str) -> BaseChatModel:
    """Initializes and returns the LangChain chat model based on the model name."""
    google_api_key_str = _get_google_api_key()

    try:
        if model.startswith("gpt-"):
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise click.ClickException(
                    "Error: OPENAI_API_KEY environment variable not set."
                )
            # Pass raw string and ignore Mypy SecretStr complaint
            return ChatOpenAI(model=model, api_key=api_key, temperature=0.7)
        elif model.startswith("claude-"):
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise click.ClickException(
                    "Error: ANTHROPIC_API_KEY environment variable not set."
                )
            # Pass raw string and ignore Mypy SecretStr complaint
            # Also ignore missing timeout argument if it's optional
            return ChatAnthropic(model_name=model, api_key=api_key, temperature=0.7)
        elif model.startswith("gemini-"):
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
            # Pass raw string and ignore Mypy SecretStr complaint
            # Also ignore missing optional arguments
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=google_api_key_str,
                temperature=0.7,
                convert_system_message_to_human=True,
            )
        else:
            raise click.ClickException(f"🚫 Unsupported model: {model}")
    except Exception as e:
        raise click.ClickException(f"Error initializing AI model: {e}") from e


# Helper function to prepare context (diff, repo, branch)
def _prepare_context() -> str:
    """
    Gets the repository context (name, branch, diff).

    Returns:
        str: The formatted diff string.
    Raises:
        click.ClickException: If no staged changes are found.
    """
    diff = get_staged_changes_diff()
    if not diff:
        raise click.ClickException("⚠️ Warning: No staged changes found. Exiting.")

    repo_name = get_repository_name()
    branch_name = get_current_branch_name()
    return f"{repo_name}/{branch_name}\n\n{diff}"


# Helper function to build the final prompt
def _build_prompt(
    explanation: str, formatted_diff: str, template: Optional[str]
) -> str:
    """Builds the complete prompt for the AI model."""
    system_message = default_system_message
    if template:
        system_message += adding_template
        system_message += template

    if explanation:
        diff_message = build_user_message(explanation, formatted_diff)
    else:
        diff_message = formatted_diff

    return f"{system_message}\n\n{diff_message}"


# Helper function to handle commit message editing and creation
def _handle_commit(commit_message: str, commit_flag: bool) -> None:
    """
    Writes message, optionally opens editor, and creates the commit.

    Raises:
        click.ClickException: On file I/O errors or if the commit is aborted.
    """
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
    if not commit_flag:
        try:
            click.edit(filename=commit_msg_path)
            with open(commit_msg_path, "r") as f:
                final_commit_message = f.read().strip()
        except click.UsageError as e:
            click.secho(f"Could not open editor: {e}", fg="yellow")
            click.secho(f"Using generated message:\n\n{commit_message}\n", fg="yellow")
        except IOError as e:
            raise click.ClickException(
                f"Error reading commit message file after edit: {e}"
            ) from e

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
    """CommitAi CLI group."""
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
    default="gemini-2.5-pro-preview-03-25",
    help=(
        "Set the engine model (e.g., 'gpt-4', 'claude-3-opus-20240229', "
        "'gemini-2.5-pro-preview-03-25'). Ensure API key env var is set "
        "(OPENAI_API_KEY, ANTHROPIC_API_KEY, "
        "GOOGLE_API_KEY/GEMINI_API_KEY/GOOGLE_GENERATIVE_AI_API_KEY)."
    ),
)
def generate_message(
    description: Tuple[str, ...],
    commit: bool,
    template: Optional[str],
    add: bool,
    model: str,
) -> None:
    """Generates a commit message based on staged changes and description."""
    explanation = " ".join(description)

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

    if template:
        click.secho(
            "⚠️ Warning: The --template/-t option is deprecated. Use environment "
            "variable TEMPLATE_COMMIT or `commitai-create-template` command.",
            fg="yellow",
        )
    final_template = template or get_commit_template()

    input_message = _build_prompt(explanation, formatted_diff, final_template)

    click.clear()
    click.secho(
        "\n\n🧠 Analyzing the changes and generating a commit message...\n\n",
        fg="blue",
        bold=True,
    )
    try:
        assert llm is not None
        ai_message = llm.invoke(input=input_message)
        commit_message = ai_message.content
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
    "--model",
    "-m",
    default="gemini-2.5-pro-preview-03-25",
    help="Set the engine model to be used.",
)
@click.pass_context
def commitai_alias(
    ctx: click.Context,
    description: Tuple[str, ...],
    add: bool,
    commit: bool,
    model: str,
) -> None:
    """Alias for the 'generate' command."""
    ctx.forward(
        generate_message, description=description, add=add, commit=commit, model=model
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
