# -*- coding: utf-8 -*-
import click
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from commitai.git import (
    create_commit,
    get_commit_template,
    get_current_branch_name,
    get_repository_name,
    get_staged_changes_diff,
    perform_git_reset,
    save_commit_template,
    stage_all_changes,
)


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def cli():
    pass


@cli.command()
@click.argument("steps_back", type=int)
def back(steps_back):
    perform_git_reset(steps_back)
    click.echo(f"Successfully performed git reset HEAD~{steps_back}.")


@cli.command()
@click.argument("template_content")
def create_template(template_content):
    save_commit_template(template_content)
    click.echo("Template saved successfully.")


@cli.command()
@click.argument("explanation", required=False)
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
    help="Specify a commit message template",
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
    default="claude-opus",
    help="Set the engine model to be used",
)
def main(explanation, commit, template, add, model):
    if model == "gpt-4":
        llm = ChatOpenAI(model_name="gpt-4")
    elif model == "claude-opus":
        llm = ChatAnthropic(model="claude-3-opus-20240229")
    else:
        click.echo(f"Unsupported model: {model}")
        return

    if add:
        stage_all_changes()

    diff = get_staged_changes_diff()
    if not diff:
        click.echo("Warning: No staged changes found. Exiting.")
        return

    repo_name = get_repository_name()
    branch_name = get_current_branch_name()
    formatted_diff = f"{repo_name}/{branch_name}\n\n{diff}"

    if not template:
        template = get_commit_template()

    system_message = (
        "You are a helpful git commit assistant. "
        "You will receive a git diff and generate a commit message."
        "Try to be meaningful and avoid generic messages."
    )
    if template:
        system_message += "The message should follow this template: "
        system_message += template

    user_message = formatted_diff
    if explanation:
        user_message = (
            f"Here is a high-level explanation of the commit: "
            f"{explanation}\n\n{user_message}"
        )

    input_message = f"{system_message}\n\n{user_message}"
    ai_message = llm.invoke(input=input_message)
    commit_message = ai_message.content

    if commit:
        create_commit(commit_message)
        click.echo(f"Committed message:\n\n{commit_message}")
    else:
        # Open default git editor for editing the commit message
        with open(".git/COMMIT_EDITMSG", "w") as f:
            f.write(commit_message)
        click.edit(filename=".git/COMMIT_EDITMSG")

        # Read the edited commit message
        with open(".git/COMMIT_EDITMSG", "r") as f:
            edited_commit_message = f.read().strip()

        # Create the commit with the edited message
        create_commit(edited_commit_message)
        click.echo(f"Committed message:\n\n{edited_commit_message}")


if __name__ == "__main__":
    cli()
