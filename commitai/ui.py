# File: commitai/ui.py
import os
from typing import Generator

import questionary
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.spinner import Spinner
from rich.text import Text
from rich.theme import Theme

from commitai.git import get_unstaged_files, stage_file

# Custom theme for "State of the Art" look
theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "header": "bold magenta",
        "token": "white",
    }
)

console = Console(theme=theme)

ASCII_ART_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "ascii-art.txt"
)


class RichUI:
    def __init__(self):
        self.console = console

    def render_header(self):
        """Renders the persistent header with ASCII art."""
        self.console.clear()
        if os.path.exists(ASCII_ART_PATH):
            with open(ASCII_ART_PATH, "r") as f:
                art = f.read()
                # Center and colorize the art
                self.console.print(
                    Panel(
                        Text(art, justify="center", style="header"),
                        border_style="blue",
                        title="CommitAI",
                        subtitle="State of the Art Commit Assistant",
                    )
                )
        else:
            self.console.print(Panel("CommitAI", style="header"))
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

        self.console.print(
            "[info]📝 Unstaged changes detected. Let's select what to include:[/info]"
        )

        selected_files = questionary.checkbox(
            "Select files to stage:",
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
        Handles the streaming of the agent response.
        Displays a spinner for 'thought' events and streams text for 'token' events.
        """
        content = ""
        current_status = "Thinking..."

        # We use a Live display to update the panel in real-time
        with Live(
            console=self.console, refresh_per_second=10, vertical_overflow="visible"
        ) as live:
            # Initial state
            live.update(Spinner("dots", text=current_status))

            for event in stream_generator:
                event_type = event.get("type")
                event_content = event.get("content", "")

                if event_type == "thought":
                    # Update the status spinner text
                    current_status = event_content
                    # We can print ephemeral status updates above final panel if desired
                    # For now just keep the spinner active.
                    # Strategy: Use the Live component for the MAIN output.
                    # 'Thoughts' can be ephemeral logs above it or
                    # updates to spinner.
                    live.update(Spinner("dots", text=f"[blue]{current_status}[/blue]"))

                elif event_type == "token":
                    # Once we start getting tokens, switch to showing content in a Panel
                    content += event_content
                    live.update(
                        Panel(
                            Markdown(content),
                            title="[bold green]Generated Commit Message[/bold green]",
                            border_style="green",
                        )
                    )

        return content

    def confirm_action(self, message: str) -> bool:
        return bool(Confirm.ask(f"[bold]{message}[/bold]"))

    def print_error(self, message: str):
        self.console.print(f"[error]❌ {message}[/error]")

    def print_success(self, message: str):
        self.console.print(f"[success]✅ {message}[/success]")
