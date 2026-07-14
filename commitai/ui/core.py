from typing import Generator

import questionary
from rich.console import Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.spinner import Spinner
from rich.text import Text

from commitai.git.core import get_unstaged_files, stage_file

from .theme import ASCII_ART, console


class RichUI:
    def __init__(self):
        self.console = console

    def render_header(self):
        """Renders the persistent header with ASCII art."""
        self.console.clear()
        self.console.print(Text(ASCII_ART, style="header"))
        self.console.print()

    def interactive_staging(self) -> bool:
        """
        Wizard to stage files interactively.
        Returns True if files were staged, False otherwise.
        """
        unstaged = get_unstaged_files()
        if not unstaged:
            return False

        choices = [questionary.Choice(f, checked=False) for f in unstaged]
        SELECT_ALL_OPTION = ">> Select All <<"
        choices.append(questionary.Choice(SELECT_ALL_OPTION, checked=False))

        self.console.print(
            "[info]📝 Unstaged changes detected. Let's select what to include:[/info]\n"
        )

        selected_files = questionary.checkbox(
            "Select files:",
            choices=choices,
            style=questionary.Style(
                [
                    ("qmark", "fg:#673ab7 bold"),
                    ("question", "bold"),
                    ("answer", "fg:#2196f3 bold"),
                    ("pointer", "fg:#673ab7 bold"),
                    ("highlighted", "fg:#673ab7 bold"),
                    ("selected", "fg:#cc5454"),
                    ("separator", "fg:#cc5454"),
                    ("instruction", ""),
                    ("text", ""),
                    ("disabled", "fg:#858585 italic"),
                ]
            ),
        ).ask()

        if selected_files:
            if SELECT_ALL_OPTION in selected_files:
                selected_files = unstaged

            with self.console.status("[bold blue]Staging files...", spinner="dots"):
                for file_path in selected_files:
                    stage_file(file_path)
            self.console.print(
                f"[success]✅ Staged {len(selected_files)} files.[/success]"
            )
            return True

        return False

    def stream_response(self, stream_generator: Generator):
        """
        Handles the streaming of the agent response with distinct UI boxes.
        """
        tool_log: list[str] = []
        message_content = ""
        current_thought = "Initializing..."

        def generate_layout():
            items = []
            items.append(
                Panel(
                    Spinner("dots", text=f" {current_thought}"),
                    title="[bold magenta]Thinking[/bold magenta]",
                    border_style="magenta",
                    padding=(0, 1),
                )
            )

            if tool_log:
                items.append(
                    Panel(
                        "\n".join(tool_log),
                        title="[bold blue]Tools Used[/bold blue]",
                        border_style="blue",
                    )
                )

            if message_content:
                items.append(
                    Panel(
                        Markdown(message_content),
                        title=("[bold green]Generated Commit Message[/bold green]"),
                        border_style="green",
                    )
                )

            return Group(*items)

        with Live(
            console=self.console, refresh_per_second=10, vertical_overflow="visible"
        ) as live:
            live.update(generate_layout())

            for event in stream_generator:
                etype = event.get("type")
                content = event.get("content", "")

                if etype == "thought":
                    current_thought = content

                elif etype in ("tool_use", "tool_output"):
                    tool_log.append(content)
                    current_thought = "Executing tools..."

                elif etype == "token":
                    if isinstance(content, list):
                        content = "".join(str(c) for c in content)
                    message_content += str(content)
                    current_thought = "Drafting message..."

                elif etype == "error":
                    current_thought = f"[red]Error: {content}[/red]"

                live.update(generate_layout())

        return message_content

    def confirm_action(self, message: str) -> bool:
        return bool(Confirm.ask(f"[bold]{message}[/bold]", default=True))

    def print_error(self, message: str):
        self.console.print(f"[error]❌ {message}[/error]")

    def print_success(self, message: str):
        self.console.print(f"[success]✅ {message}[/success]")
