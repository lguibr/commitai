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
    save_commit_template,
    stage_all_changes,
)


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def cli():
    pass


@cli.command()
@click.argument("description_or_command", nargs=-1, type=click.UNPROCESSED)
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
def main(description_or_command, commit, template, add, model):

    description_or_command_exists = len(description_or_command) > 1
    is_command = (
        description_or_command[0] == "create-template"
        if description_or_command_exists
        else False
    )

    if is_command:
        if len(description_or_command) > 1:
            template_content = " ".join(description_or_command[1:])
            save_commit_template(template_content)
            click.echo("Template saved successfully.")
            return
        else:
            click.echo("Please provide the template content.")
        return

    explanation = " ".join(description_or_command)
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
