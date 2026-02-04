# File: commitai/ui.py
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

ASCII_ART = r"""
 ....                        ++*++                       :::::
..............              ++++++              -:::::::-:- :::
.............:..              +**              ==--::-  :::::::
  ...       :...           =++++++=            ---
            ....      ***+++++++++++++++       ::-
             ...     ***+++****++++++++++*     ::-
             ...     ***+++****+++++++++++     :::       -----
             ...::::-+**++   **+++  ++++++=---=:----------- ---
               ...-:-+**+++++**++++++++++++-::==---------------
              ...    ***++++++*+++++++*++* :::- -------  -----
             ::::     ####***********###*  ----  ------
  .....      ...        ###**####****##   -----:  ---    -----
.........   ...               +++        :::::::: ---- ---------
...   .....:..       ++++++++**+        :::-   ::-  ------   ---
..........            +**+++            -:::::::::     ---------
 .......                                  -:::::         ------
"""


class RichUI:
    def __init__(self):
        self.console = console

    def render_header(self):
        """Renders the persistent header with ASCII art."""
        self.console.clear()
        # Center and colorize the art
        # Center and colorize the art
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
        # Add "Select All" option at the end as requested
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
            # Handle "Select All" logic
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
        from rich.console import Group

        tool_log: list[str] = []
        message_content = ""
        current_thought = "Initializing..."

        def generate_layout():
            items = []

            # 1. Thinking Box (Spinner + Current Status)
            items.append(
                Panel(
                    Spinner("dots", text=f" {current_thought}"),
                    title="[bold magenta]Thinking[/bold magenta]",
                    border_style="magenta",
                    padding=(0, 1),
                )
            )

            # 2. Tools Box (Only if tools have been used)
            if tool_log:
                # Show tool events (User requested "tools used" box)
                items.append(
                    Panel(
                        "\n".join(tool_log),
                        title="[bold blue]Tools Used[/bold blue]",
                        border_style="blue",
                    )
                )

            # 3. Message Box (Only if content exists)
            if message_content:
                items.append(
                    Panel(
                        Markdown(message_content),
                        title=("[bold green]Generated Commit Message[/bold green]"),
                        border_style="green",
                    )
                )

            return Group(*items)

        # Use Live display
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
                    current_thought = "Executing tools..."  # Update status too

                elif etype == "token":
                    if isinstance(content, list):
                        content = "".join(str(c) for c in content)
                    message_content += str(content)
                    current_thought = "Drafting message..."

                elif etype == "error":
                    current_thought = f"[red]Error: {content}[/red]"
                    # Ensure we don't lose the error visibility

                live.update(generate_layout())

        return message_content

    def confirm_action(self, message: str) -> bool:
        return bool(Confirm.ask(f"[bold]{message}[/bold]", default=True))

    def print_error(self, message: str):
        self.console.print(f"[error]❌ {message}[/error]")

    def print_success(self, message: str):
        self.console.print(f"[success]✅ {message}[/success]")
