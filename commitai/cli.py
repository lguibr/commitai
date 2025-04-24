# File: commitai/cli.py
# -*- coding: utf-8 -*-

import os

import click
# Use built-in imports from langchain
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
# Conditional import for Google Generative AI
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

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
    default="gemini-2.5-pro-preview-03-25",
    help=(
        "Set the engine model to be used (e.g., 'gpt-4', 'claude-3-opus-20240229', 'gemini-pro'). "
        "Ensure you have the corresponding API key set (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY)."
    ),
)
def generate_message(description, commit, template, add, model):
    explanation = " ".join(description)

    # Model loading logic
    if model.startswith("gpt-"):
        llm = ChatOpenAI(model_name=model, temperature=0.7)
    elif model.startswith("claude-"):
        llm = ChatAnthropic(model_name=model, temperature=0.7)
    elif model.startswith("gemini-"):
        if ChatGoogleGenerativeAI is None:
            click.secho("Error: 'langchain-google-genai' is not installed. Run 'pip install langchain-google-genai'", fg="red", bold=True)
            return
        # Note: Ensure GOOGLE_API_KEY is set in the environment
        llm = ChatGoogleGenerativeAI(model=model, temperature=0.7, convert_system_message_to_human=True)
    else:
        click.secho(f"🚫 Unsupported model: {model}", fg="red", bold=True)
        return

    if add:
        stage_all_changes()

    click.secho(
        "\n🔍 Looking for a native pre-commit hook and running it\n",
        fg="blue",
        bold=True,
    )

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

    # Clear the terminal using click
    click.clear()

    repo_name = get_repository_name()
    branch_name = get_current_branch_name()
    formatted_diff = f"{repo_name}/{branch_name}\n\n{diff}"

    if not template:
        template = get_commit_template()
    system_message = ""
    if template:
        system_message += default_system_message
        system_message += adding_template
        system_message += template

    if explanation:
        diff_message = build_user_message(explanation, formatted_diff)
    else:
        diff_message = formatted_diff

    input_message = f"{system_message}\n\n{diff_message}"

    click.secho(
        "\n\n🧠 Analyzing the changes and generating a commit message...\n\n",
        fg="blue",
        bold=True,
    )

    # Invoke the model
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
