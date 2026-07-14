import os
import sys
from typing import Optional, Tuple

import click

from commitai import __version__
from commitai.agent.core import create_commit_agent
from commitai.cli.config import _initialize_llm
from commitai.git.core import (
    create_commit,
    get_current_branch_name,
    get_repository_name,
    get_staged_changes_diff,
    run_pre_commit_hook,
    stage_all_changes,
)
from commitai.template import get_template, save_template
from commitai.types import TemplateType
from commitai.ui.core import RichUI


def _prepare_context() -> str:
    diff = get_staged_changes_diff()
    if not diff:
        raise click.ClickException("⚠️ Warning: No staged changes found. Exiting.")

    repo_name = get_repository_name()
    branch_name = get_current_branch_name()
    return f"{repo_name}/{branch_name}\n\n{diff}"


def _handle_commit(commit_message: str, commit_flag: bool) -> None:
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
        try:
            if ui.confirm_action("Commit with this message?"):
                pass
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
@click.version_option(__version__, "--version", "-v", message="%(version)s")
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
    default="gemini-flash-latest",
    help=(
        "Set the engine model (default: gemini-flash-latest). "
        "Only Google Gemini models are supported "
        "('gemini-flash-latest', 'gemini-pro-latest'). "
        "Ensure GOOGLE_API_KEY is set."
    ),
)
@click.option(
    "--deep",
    "-d",
    is_flag=True,
    help="Use the deeper reasoning model (gemini-pro-latest).",
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
    ui = RichUI()
    ui.render_header()

    explanation = " ".join(description)

    if deep:
        if model == "gemini-flash-latest":
            model = "gemini-pro-latest"

    llm = _initialize_llm(model)

    if not add:
        staged = ui.interactive_staging()
        if staged:
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

    agent_pipeline = create_commit_agent(llm)

    if review:
        ui.console.print("\n[info]🔎 Reviewing staged changes...[/info]")
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
        final_template_content = get_template(TemplateType.COMMIT)

    try:
        assert llm is not None
        inputs = {"diff": formatted_diff, "explanation": explanation}
        if final_template_content:
            inputs["template"] = final_template_content

        stream_gen = agent_pipeline.stream(inputs)
        commit_message = ui.stream_response(stream_gen)

    except Exception as e:
        ui.print_error(f"Error during AI generation: {e}")
        sys.exit(1)

    _handle_commit(commit_message, commit)


@cli.command(name="create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
def create_template_command(template_content: Tuple[str, ...]) -> None:
    """Saves a repository-specific commit template."""
    ui = RichUI()

    content = " ".join(template_content)
    if content:
        save_template(TemplateType.COMMIT, content)
        ui.print_success("Template saved successfully.")
    else:
        ui.print_error("Please provide the template content.")


@cli.command(name="manage-templates")
def manage_templates_command() -> None:
    """Manage local repository templates for commits and PRs."""
    import questionary

    from commitai.template import delete_template, get_template, save_template
    from commitai.types import TemplateType

    ui = RichUI()

    choice = questionary.select(
        "Which template do you want to manage?",
        choices=["Commit Template", "Pull Request Template", "Exit"],
    ).ask()

    if choice == "Exit" or not choice:
        return

    template_type = (
        TemplateType.COMMIT if choice == "Commit Template" else TemplateType.PR
    )

    action = questionary.select(
        f"Manage {choice}:", choices=["View", "Edit", "Delete", "Back"]
    ).ask()

    if action == "Back" or not action:
        manage_templates_command()
        return

    if action == "View":
        content = get_template(template_type)
        if content:
            ui.console.print(
                f"\n[bold green]Current {choice}:[/bold green]\n{content}\n"
            )
        else:
            ui.console.print(
                f"\n[bold yellow]No {choice} is currently set.[/bold yellow]\n"
            )

    elif action == "Edit":
        current_content = get_template(template_type) or ""
        import click

        new_content = click.edit(text=current_content)
        if new_content is not None:
            save_template(template_type, new_content.strip())
            ui.print_success(f"{choice} updated successfully.")
        else:
            ui.print_error("Edit aborted.")

    elif action == "Delete":
        delete_template(template_type)
        ui.print_success(f"{choice} deleted successfully.")


@cli.command(name="pr")
@click.argument("feedback", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--branch",
    "-b",
    default="main",
    help="Target branch to compare against (default: main).",
)
@click.option(
    "--model",
    "-m",
    default="gemini-flash-latest",
    help="Set the engine model (default: gemini-flash-latest).",
)
def pr_command(
    feedback: Tuple[str, ...],
    branch: str,
    model: str,
) -> None:
    """Generate a Pull Request description."""
    import subprocess

    from commitai.agent import create_pr_agent
    from commitai.template import get_template
    from commitai.types import TemplateType

    ui = RichUI()
    ui.render_header()

    feedback_str = " ".join(feedback)
    llm = _initialize_llm(model)

    try:
        # Get diff against target branch
        diff = subprocess.check_output(["git", "diff", f"{branch}...HEAD"]).decode(
            "utf-8"
        )
        if not diff:
            ui.print_error(f"No changes found between {branch} and HEAD.")
            sys.exit(1)
    except subprocess.CalledProcessError:
        ui.print_error(f"Could not compare against branch '{branch}'. Does it exist?")
        sys.exit(1)

    template = get_template(TemplateType.PR)

    agent_pipeline = create_pr_agent(llm)

    try:
        assert llm is not None
        inputs = {
            "diff": diff,
            "feedback": feedback_str,
            "branch": branch,
            "template": template,
        }

        stream_gen = agent_pipeline.stream(inputs)
        pr_description = ui.stream_response(stream_gen)

        # Output logic
        ui.console.print("\n[bold green]Final PR Description:[/bold green]\n")
        ui.console.print(pr_description)

    except Exception as e:
        ui.print_error(f"Error during AI generation: {e}")
        sys.exit(1)


@click.command(
    name="commitai",
    context_settings={"ignore_unknown_options": True},
)
@click.version_option(__version__, "--version", "-v", message="%(version)s")
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
    default="gemini-flash-latest",
    help="Set the engine model to be used.",
)
@click.option(
    "--deep",
    "-d",
    is_flag=True,
    help="Use the deeper reasoning model (gemini-pro-latest).",
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
