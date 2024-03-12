# -*- coding: utf-8 -*-
import os

import click
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

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


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def cli():
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
def generate_message(description, commit, template, add, model):
    explanation = " ".join(description)
    if model == "gpt-4":
        llm = ChatOpenAI(model_name="gpt-4")
    elif model == "claude-opus":
        llm = ChatAnthropic(model="claude-3-opus-20240229")
    else:
        click.secho(f"🚫 Unsupported model: {model}", fg="red", bold=True)
        return

    if add:
        stage_all_changes()

    if not run_pre_commit_hook():
        click.secho(
            "🚫 Pre-commit hook failed. Aborting commit.",
            fg="red",
            bold=True,
        )
        return

    diff = get_staged_changes_diff()
    if not diff:
        click.secho(
            "⚠️ Warning: No staged changes found. Exiting.",
            fg="yellow",
            bold=True,
        )
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
        system_message += " The message should follow this template: "
        system_message += template

    user_message = formatted_diff
    if explanation:
        user_message = (
            f"Here is a high-level explanation of the commit: {explanation}"
            f"\n\n{user_message}"
        )

    input_message = f"{system_message}\n\n{user_message}"
    ai_message = llm.invoke(input=input_message)
    commit_message = ai_message.content

    repo_path = get_repository_name()
    commit_msg_path = os.path.join(repo_path, ".git", "COMMIT_EDITMSG")
    with open(commit_msg_path, "w") as f:
        f.write(commit_message)

    if not commit:
        click.edit(filename=commit_msg_path)

    with open(commit_msg_path, "r") as f:
        final_commit_message = f.read().strip()

    create_commit(final_commit_message)
    click.secho(
        f"\n\n✅ Committed message:\n\n{final_commit_message}\n\n",
        fg="green",
        bold=True,
    )


@cli.command(name="create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
def create_template_command(template_content):
    template_content = " ".join(template_content)
    if template_content:
        save_commit_template(template_content)
        click.secho("📝 Template saved successfully.", fg="green")
    else:
        click.secho("❗ Please provide the template content.", fg="red")


@click.command(name="commitai")
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
@click.pass_context
def commitai(ctx, description, add, commit):
    if add:
        stage_all_changes()
    ctx.invoke(
        generate_message,
        description=description,
        add=add,
        commit=commit,
    )


@click.command(name="commitai-create-template")
@click.argument("template_content", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def commitai_create_template(ctx, template_content):
    ctx.invoke(create_template_command, template_content=template_content)


cli.add_command(commitai)
cli.add_command(commitai_create_template)


if __name__ == "__main__":
    cli()
