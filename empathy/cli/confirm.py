"""Textual confirmation screen for agent draft review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static, TextArea

ConfirmAction = Literal["accept", "edit", "reject", "human"]


@dataclass
class ConfirmResult:
    action: ConfirmAction
    edited_content: str | None = None


class ConfirmApp(App[ConfirmResult]):
    """Show an agent draft and capture the controller's decision."""

    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }
    #draft {
        width: 80%;
        height: auto;
        max-height: 55%;
        border: round $primary;
        padding: 1 2;
        margin-bottom: 1;
    }
    #editor {
        width: 80%;
        height: 10;
        border: round $warning;
        margin-bottom: 1;
    }
    #hint {
        width: 80%;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("a", "accept", "Accept", show=True),
        Binding("e", "edit", "Edit", show=True),
        Binding("r", "reject", "Reject", show=True),
        Binding("h", "human_type", "Type yourself", show=True),
        Binding("ctrl+s", "confirm_edit", "Save", show=False, priority=True),
        Binding("escape", "cancel_edit", "Cancel", show=False),
    ]

    def __init__(self, draft_content: str) -> None:
        super().__init__()
        self._draft_content = draft_content
        self._editing = False

    def compose(self) -> ComposeResult:
        # TextArea is NOT included here; it is mounted dynamically in action_edit.
        yield Static(self._draft_content, id="draft")
        yield Static(
            "[bold][a][/bold]ccept  [bold][e][/bold]dit  "
            "[bold][r][/bold]eject  [bold][h][/bold]uman-type",
            id="hint",
        )
        yield Footer()

    def action_accept(self) -> None:
        if not self._editing:
            self.exit(ConfirmResult(action="accept"))

    def action_reject(self) -> None:
        if not self._editing:
            self.exit(ConfirmResult(action="reject"))

    def action_human_type(self) -> None:
        if not self._editing:
            self.exit(ConfirmResult(action="human"))

    def action_edit(self) -> None:
        if self._editing:
            return
        self._editing = True
        self.query_one("#draft", Static).display = False
        editor = TextArea(self._draft_content, id="editor")
        self.mount(editor, before=self.query_one("#hint", Static))
        editor.focus()

    def action_confirm_edit(self) -> None:
        if not self._editing:
            return
        text = self.query_one("#editor", TextArea).text.strip()
        if text:
            self.exit(ConfirmResult(action="edit", edited_content=text))

    def action_cancel_edit(self) -> None:
        if not self._editing:
            return
        self._editing = False
        self.query_one("#editor", TextArea).remove()
        self.query_one("#draft", Static).display = True


def confirm_draft(draft_content: str) -> ConfirmResult:
    """Run the Textual confirmation UI synchronously and return the result."""
    result = ConfirmApp(draft_content).run()
    return result if result is not None else ConfirmResult(action="reject")
