"""Textual TUI for empathy: split-pane dialogue controller."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Input, RichLog, Static, TextArea

from empathy.cli.commands import COMMANDS, get_suggestions
from empathy.core.models import ClarificationMessage, Draft
from empathy.extensions.skills import Skill
from empathy.modes.session import DialogueSession


@dataclass
class ConfirmState:
    """State while waiting for draft confirmation."""

    draft_content: str
    selected_idx: int = 0
    options: list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.options is None:
            self.options = [
                ("a", "Accept"),
                ("e", "Edit"),
                ("r", "Reject"),
                ("h", "Type yourself"),
            ]

    @property
    def selected_option(self) -> str:
        assert self.options is not None
        return self.options[self.selected_idx][0]


class TranscriptPanel(RichLog):
    """Right panel showing dialogue transcript, auto-refreshes."""

    def __init__(self, transcript_path: Path, side: str, show_tools: bool = True, **kwargs: Any) -> None:
        super().__init__(wrap=True, highlight=True, markup=True, **kwargs)
        self._transcript_path = transcript_path
        self._side = side
        self._show_tools = show_tools
        self._last_count = 0

    def refresh_transcript(self) -> None:
        from empathy.storage.transcript import read_turns

        try:
            turns = read_turns(self._transcript_path)
        except Exception:
            return
        if len(turns) == self._last_count:
            return
        self.clear()
        for turn in turns:
            speaker_color = "cyan" if turn.speaker == "therapist" else "yellow"
            source_hint = ""
            if turn.source.value == "human":
                source_hint = " [dim](human)[/dim]"
            elif turn.source.value == "agent_edit":
                source_hint = " [dim](edited)[/dim]"
            self.write(
                f"[bold {speaker_color}]{turn.speaker.upper()}[/bold {speaker_color}]"
                f"{source_hint}\n{turn.content}\n"
            )
        self._last_count = len(turns)
        self.scroll_end(animate=False)


class SuggestionWidget(Static):
    """Shows slash command completions above the input."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self.display = False

    def update_suggestions(self, suggestions: list[str], prefix: str) -> None:  # noqa: ARG002
        if not suggestions:
            self.display = False
            return
        lines = []
        for s in suggestions[:5]:
            cmd_name = s[1:].split()[0]
            info = COMMANDS.get(cmd_name)
            desc = info["description"] if info else ""
            lines.append(f"  [cyan]{s}[/cyan]  [dim]{desc}[/dim]")
        self.update("\n".join(lines))
        self.display = True

    def hide(self) -> None:
        self.display = False
        self.update("")


class CommandInput(Input):
    """Input widget with slash command tab completion."""

    def __init__(self, suggestions_widget: SuggestionWidget, **kwargs: Any) -> None:
        super().__init__(placeholder="Type instruction or /command...", **kwargs)
        self._suggestions_widget = suggestions_widget
        self._suggestions: list[str] = []
        self._suggestion_idx = -1

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        if value.startswith("/"):
            self._suggestions = get_suggestions(value)
            self._suggestion_idx = -1
            self._suggestions_widget.update_suggestions(self._suggestions, value)
        else:
            self._suggestions = []
            self._suggestions_widget.hide()

    def on_key(self, event: object) -> None:
        from textual.events import Key

        if not isinstance(event, Key):
            return
        if event.key == "tab" and self._suggestions:
            event.prevent_default()
            event.stop()
            self._suggestion_idx = (self._suggestion_idx + 1) % len(self._suggestions)
            self.value = self._suggestions[self._suggestion_idx]
            self.cursor_position = len(self.value)


class ConfirmWidget(Static, can_focus=True):
    """Inline confirmation widget. Shows draft + options above input."""

    BINDINGS = [
        Binding("a", "accept", show=False),
        Binding("e", "start_edit", show=False),
        Binding("r", "reject", show=False),
        Binding("h", "human_type", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("enter", "confirm_selection", show=False),
        Binding("tab", "refine", "Refine (Tab)", show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self.display = False
        self._state: ConfirmState | None = None
        self._callback: Callable[[str], None] | None = None

    def show_confirm(self, draft_content: str, callback: Callable[[str], None]) -> None:
        self._state = ConfirmState(draft_content=draft_content)
        self._callback = callback
        self.display = True
        self._render_options()

    def _render_options(self) -> None:
        if not self._state:
            return
        assert self._state.options is not None
        lines = ["[bold yellow]Agent Draft:[/bold yellow]"]
        for line in self._state.draft_content.split("\n"):
            lines.append(f"  {line}")
        lines.append("")
        for i, (_, label) in enumerate(self._state.options):
            if i == self._state.selected_idx:
                lines.append(f"  [bold cyan]▶ {i + 1}. {label}[/bold cyan]")
            else:
                lines.append(f"  [dim]  {i + 1}. {label}[/dim]")
        lines.append("")
        lines.append("  [dim]Tab → refine instruction[/dim]")
        self.update("\n".join(lines))

    def action_move_up(self) -> None:
        if self._state:
            assert self._state.options is not None
            self._state.selected_idx = (self._state.selected_idx - 1) % len(self._state.options)
            self._render_options()

    def action_move_down(self) -> None:
        if self._state:
            assert self._state.options is not None
            self._state.selected_idx = (self._state.selected_idx + 1) % len(self._state.options)
            self._render_options()

    def action_confirm_selection(self) -> None:
        if self._state and self._callback:
            self._execute(self._state.selected_option)

    def action_accept(self) -> None:
        self._execute("a")

    def action_reject(self) -> None:
        self._execute("r")

    def action_human_type(self) -> None:
        self._execute("h")

    def action_refine(self) -> None:
        self._execute("refine")

    def action_start_edit(self) -> None:
        self._execute("e")

    def _execute(self, key: str) -> None:
        if self._callback:
            cb = self._callback
            self._state = None
            self._callback = None
            self.display = False
            self.update("")
            cb(key)


class EditArea(TextArea):
    """Multiline text area for editing drafts and typing human responses."""

    BINDINGS = [
        Binding("enter", "submit", "Submit (Enter)", priority=True, show=True),
        Binding("ctrl+j", "insert_newline", "Newline (Ctrl+Enter)", show=True),
        Binding("escape", "cancel", "Cancel (Esc)", show=True),
    ]

    class Submitted(Message):
        def __init__(self, value: str, control: TextArea) -> None:
            self.value = value
            self._control = control
            super().__init__()

        @property
        def control(self) -> TextArea:
            return self._control

    class Canceled(Message):
        def __init__(self, control: TextArea) -> None:
            self._control = control
            super().__init__()

        @property
        def control(self) -> TextArea:
            return self._control

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.show_line_numbers = False

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self.text, self))

    def action_insert_newline(self) -> None:
        self.insert("\n")

    def action_cancel(self) -> None:
        self.post_message(self.Canceled(self))


class StatusBar(Static):
    """Bottom 1-row status line."""

    def __init__(self, session: DialogueSession, skills: dict[str, Skill], **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._session = session
        self._skills = skills
        self._tool_calls = 0

    def increment_tool_calls(self) -> None:
        """Increment tool call counter."""
        self._tool_calls += 1

    def refresh_status(self) -> None:
        state = self._session.floor_status()
        holder = state.get("floor_holder")
        turn_num = state.get("turn_number", 0)

        if holder == self._session.side:
            floor_str = "[green]MINE[/green]"
        elif holder:
            floor_str = f"[yellow]{holder}[/yellow]"
        else:
            floor_str = "[dim]free[/dim]"

        skills_count = len(self._skills)
        side_color = "cyan" if self._session.side == "therapist" else "yellow"
        model: str = getattr(self._session.agent, "model", "unknown")
        short_model = model

        self.update(
            f" [bold {side_color}]{self._session.side}[/bold {side_color}]"
            f" │ floor: {floor_str}"
            f" │ turn: [cyan]{turn_num}[/cyan]"
            f" │ tools: [dim]{self._tool_calls}[/dim]"
            f" │ model: [dim]{short_model}[/dim]"
            f" │ skills: [dim]{skills_count}[/dim]"
            f" │ [dim]{self._session.dialogue_dir.name}[/dim]"
        )


class EmpathyApp(App[None]):
    """Main Textual TUI for empathy."""

    CSS = """
    EmpathyApp {
        background: $background;
    }
    #main-split {
        height: 1fr;
    }
    #left-panel {
        width: 40%;
        border-right: solid $primary-darken-2;
        layout: vertical;
    }
    #left-log {
        height: 1fr;
        border-bottom: solid $primary-darken-3;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    #confirm-widget {
        height: auto;
        padding: 0 1;
        border-bottom: solid $warning-darken-2;
        overflow-x: hidden;
    }
    #confirm-widget:focus {
        background: transparent;
    }
    #suggestions {
        height: auto;
        max-height: 8;
        padding: 0 1;
        background: $surface;
        overflow-x: hidden;
    }
    #cmd-input {
        height: 3;
        dock: bottom;
    }
    #cmd-input.-hidden {
        display: none;
    }
    #edit-area {
        height: 10;
        dock: bottom;
        display: none;
        border: solid $accent;
    }
    #edit-area.-active {
        display: block;
    }
    #transcript-panel {
        width: 60%;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    #status-bar {
        height: 1;
        background: $primary-darken-3;
        dock: bottom;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        session: DialogueSession,
        skills: dict[str, Skill] | None = None,
    ) -> None:
        super().__init__()
        self._session = session
        self._skills = skills or {}
        self._waiting_for_other = False
        self._pending_edit_draft: Draft | None = None
        self._direct_human_mode = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-split"):
            with Vertical(id="left-panel"):
                yield RichLog(id="left-log", wrap=True, markup=True)
                yield ConfirmWidget(id="confirm-widget")
                yield SuggestionWidget(id="suggestions")
                # CommandInput is wired to SuggestionWidget in on_mount
                yield CommandInput(SuggestionWidget(), id="cmd-input")
                yield EditArea(id="edit-area")
            yield TranscriptPanel(
                self._session.transcript_path,
                self._session.side,
                id="transcript-panel",
            )

        yield StatusBar(self._session, self._skills, id="status-bar")

    def on_mount(self) -> None:
        # Wire CommandInput to the mounted SuggestionWidget
        suggestions = self.query_one("#suggestions", SuggestionWidget)
        cmd_input = self.query_one("#cmd-input", CommandInput)
        cmd_input._suggestions_widget = suggestions

        # Start background timers
        self.set_interval(1.0, self._refresh_transcript)
        self.set_interval(0.5, self._refresh_status)
        self.set_interval(0.5, self._check_floor)

        self._refresh_transcript()
        self._refresh_status()
        self._write_log("Type an instruction for the agent, or /help for commands.")

        if not self._session.try_acquire_floor():
            self._write_log("[dim]Waiting for floor...[/dim]")
        else:
            self._write_log("[green]Floor acquired. You may speak.[/green]")

        cmd_input.focus()

    def _write_log(self, message: str) -> None:
        try:
            log = self.query_one("#left-log", RichLog)
            log.write(message)
        except NoMatches:
            pass

    def _display_emotion_change(self, emotion_change: dict) -> None:
        """Display emotion state change in the log panel.

        Args:
            emotion_change: Dict with from/to emotion and intensity
        """
        from_emotion = emotion_change.get("from_emotion")
        from_intensity = emotion_change.get("from_intensity")
        to_emotion = emotion_change.get("to_emotion")
        to_intensity = emotion_change.get("to_intensity")
        change_direction = emotion_change.get("change_direction", "stable")
        reasoning = emotion_change.get("reasoning", "")

        # Color code based on intensity
        def intensity_color(intensity: int) -> str:
            if intensity >= 8:
                return "red"
            elif intensity >= 6:
                return "yellow"
            elif intensity >= 4:
                return "white"
            else:
                return "green"

        # Format emotion change
        if from_emotion is None:
            # Initial state
            color = intensity_color(to_intensity)
            self._write_log(
                f"[cyan]💭 Emotion:[/cyan] [{color}]{to_emotion} ({to_intensity}/10)[/{color}]"
            )
        else:
            # State transition
            from_color = intensity_color(from_intensity)
            to_color = intensity_color(to_intensity)

            # Direction indicator
            if change_direction == "increasing":
                arrow = "↑"
            elif change_direction == "decreasing":
                arrow = "↓"
            else:
                arrow = "→"

            self._write_log(
                f"[cyan]💭 Emotion:[/cyan] [{from_color}]{from_emotion} {from_intensity}[/{from_color}] "
                f"{arrow} [{to_color}]{to_emotion} {to_intensity}[/{to_color}]"
            )

        # Show reasoning if available
        if reasoning:
            self._write_log(f"[dim]   {reasoning}[/dim]")

    def _refresh_transcript(self) -> None:
        try:
            panel = self.query_one("#transcript-panel", TranscriptPanel)
            panel.refresh_transcript()
        except NoMatches:
            pass

    def _refresh_status(self) -> None:
        try:
            status = self.query_one("#status-bar", StatusBar)
            status.refresh_status()
        except NoMatches:
            pass

    def _check_floor(self) -> None:
        """Periodic floor state check — manage waiting_for_other flag."""
        state = self._session.floor_status()
        holder = state.get("floor_holder")
        last_speaker = state.get("last_speaker")

        # Clear waiting flag once the other side has acted
        if self._waiting_for_other and not (holder is None and last_speaker == self._session.side):
            self._waiting_for_other = False

    @on(EditArea.Submitted, "#edit-area")
    def handle_edit_submitted(self, event: EditArea.Submitted) -> None:
        raw = event.value.strip()
        self._exit_edit_mode()

        if not raw:
            return

        if self._pending_edit_draft is not None:
            draft = self._pending_edit_draft
            self._pending_edit_draft = None
            turn = self._session.edit_draft(draft, raw)
            self._write_log(f"[yellow]✓ Committed (edited):[/yellow] {turn.content}")
            self._refresh_transcript()
            return

        if self._direct_human_mode:
            self._direct_human_mode = False
            turn = self._session.commit_human_turn(raw)
            self._write_log(f"[blue]✓ Committed (human):[/blue] {turn.content}")
            self._refresh_transcript()
            return

    @on(EditArea.Canceled, "#edit-area")
    def handle_edit_canceled(self, event: EditArea.Canceled) -> None:
        self._write_log("[dim]Cancelled.[/dim]")
        self._pending_edit_draft = None
        self._direct_human_mode = False
        self._exit_edit_mode()

    def _enter_edit_mode(self, initial_text: str, is_human: bool) -> None:
        try:
            cmd_input = self.query_one("#cmd-input", CommandInput)
            edit_area = self.query_one("#edit-area", EditArea)
            cmd_input.add_class("-hidden")
            edit_area.add_class("-active")

            mode = "Human Type Mode" if is_human else "Edit Draft Mode"
            self._write_log(f"[bold magenta]--- {mode} ---[/bold magenta]")
            self._write_log(
                "[magenta]Type your message. Press [bold]Enter[/bold] to submit "
                "(Ctrl+J for newline), "
                "[bold]Esc[/bold] to cancel.[/magenta]"
            )

            edit_area.text = initial_text
            edit_area.focus()
            lines = initial_text.splitlines()
            if lines:
                edit_area.cursor_location = (len(lines) - 1, len(lines[-1]))
            else:
                edit_area.cursor_location = (0, 0)
        except NoMatches:
            pass

    def _exit_edit_mode(self) -> None:
        try:
            cmd_input = self.query_one("#cmd-input", CommandInput)
            edit_area = self.query_one("#edit-area", EditArea)
            edit_area.remove_class("-active")
            cmd_input.remove_class("-hidden")
            edit_area.text = ""
            cmd_input.focus()
        except NoMatches:
            pass

    @on(Input.Submitted, "#cmd-input")
    def handle_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.control.value = ""

        with contextlib.suppress(NoMatches):
            self.query_one("#suggestions", SuggestionWidget).hide()

        if not raw:
            return

        # Floor checks
        state = self._session.floor_status()
        holder = state.get("floor_holder")
        last_speaker = state.get("last_speaker")

        if self._waiting_for_other:
            if holder is None and last_speaker == self._session.side:
                self._write_log(
                    "[yellow]Floor released. Waiting for other side to respond...[/yellow]"
                )
                return
            else:
                self._waiting_for_other = False

        if holder is not None and holder != self._session.side:
            self._write_log(f"[yellow]{holder} is composing… wait for floor.[/yellow]")
            return

        if holder is None and not self._session.try_acquire_floor():
            self._write_log("[yellow]Could not acquire floor. Try again.[/yellow]")
            return

        # Process command or instruction
        if raw.startswith("/"):
            should_exit, just_released = self._handle_command(raw)
            if just_released:
                self._waiting_for_other = True
            if should_exit:
                self.exit()
        else:
            self._process_instruction(raw)

    def _handle_command(self, cmd: str) -> tuple[bool, bool]:
        """Process a /command. Returns (should_exit, just_released)."""
        # Check for skill trigger first
        if cmd in self._skills:
            skill = self._skills[cmd]
            self._write_log(f"[dim]Activating skill:[/dim] [cyan]{skill.name}[/cyan]")
            self._process_instruction("Apply the active skill.", active_skills=[skill])
            return False, False

        base_cmd = cmd.split()[0]
        args = cmd[len(base_cmd) :].strip()

        if base_cmd == "/done":
            self._session.release_floor()
            self._write_log("[dim]Floor released. Waiting for other side...[/dim]")
            return False, True

        if base_cmd == "/quit":
            self._session.release_floor()
            return True, False

        if base_cmd == "/status":
            st = self._session.floor_status()
            self._write_log(f"[dim]{st}[/dim]")

        elif base_cmd == "/help":
            self._write_log("[bold]Available commands:[/bold]")
            for name, info in COMMANDS.items():
                self._write_log(f"  [cyan]/{name:<20}[/cyan] {info['description']}")
            if self._skills:
                self._write_log("[bold]Skills:[/bold]")
                for trigger, skill in self._skills.items():
                    self._write_log(f"  [magenta]{trigger:<20}[/magenta] {skill.name}")

        elif base_cmd == "/skills":
            if args == "reload":
                self._write_log("[dim]Reloading skills... (restart required for full reload)[/dim]")
            else:
                if self._skills:
                    for trigger, skill in self._skills.items():
                        self._write_log(
                            f"  [magenta]{trigger}[/magenta] → {skill.name}: "
                            f"{skill.description[:60]}..."
                        )
                else:
                    self._write_log("[dim]No skills loaded.[/dim]")

        elif base_cmd == "/context":
            if args == "clear":
                self._write_log(
                    "[dim]Context reset noted. Agent will re-read history on next call.[/dim]"
                )
            else:
                turns = self._session.get_transcript()
                drafts = self._session.get_draft_history()
                accepted = sum(1 for d in drafts if d.outcome == "accepted")
                rejected = sum(1 for d in drafts if d.outcome == "rejected")
                edited = sum(1 for d in drafts if d.outcome == "edited")
                self._write_log(
                    f"[bold]Context:[/bold]\n"
                    f"  Transcript turns: [cyan]{len(turns)}[/cyan]\n"
                    f"  Drafts: accepted=[green]{accepted}[/green]"
                    f" edited=[yellow]{edited}[/yellow]"
                    f" rejected=[red]{rejected}[/red]"
                )

        elif base_cmd == "/agent":
            if args.startswith("model "):
                new_model = args[6:].strip()
                if new_model:
                    self._session.agent.model = new_model
                    self._write_log(f"[green]Model switched to:[/green] [cyan]{new_model}[/cyan]")
                else:
                    self._write_log("[red]Usage: /agent model <model-id>[/red]")
            else:
                model: str = getattr(self._session.agent, "model", "unknown")
                knowledge_len = len(getattr(self._session.agent, "_knowledge", ""))
                bg_len = len(getattr(self._session.agent, "_dialogue_background", ""))
                self._write_log(
                    f"[bold]Agent info:[/bold]\n"
                    f"  Side: [cyan]{self._session.side}[/cyan]\n"
                    f"  Model: [cyan]{model}[/cyan]\n"
                    f"  Knowledge: [dim]{knowledge_len} chars[/dim]\n"
                    f"  Background: [dim]{bg_len} chars[/dim]"
                )

        elif base_cmd == "/session":
            st = self._session.floor_status()
            self._write_log(
                f"[bold]Session info:[/bold]\n"
                f"  Dialogue: [cyan]{self._session.dialogue_dir.name}[/cyan]\n"
                f"  Side: [cyan]{self._session.side}[/cyan]\n"
                f"  Turn: [cyan]{st.get('turn_number', 0)}[/cyan]\n"
                f"  Floor holder: [cyan]{st.get('floor_holder', 'none')}[/cyan]\n"
                f"  Last speaker: [cyan]{st.get('last_speaker', 'none')}[/cyan]"
            )

        elif base_cmd == "/feedback":
            drafts = self._session.get_draft_history()
            side_drafts = [d for d in drafts if d.speaker == self._session.side]

            if args == "stats":
                # Show statistics
                total = len(side_drafts)
                accepted = sum(1 for d in side_drafts if d.outcome == "accepted")
                rejected = sum(1 for d in side_drafts if d.outcome == "rejected")
                edited = sum(1 for d in side_drafts if d.outcome == "edited")
                pending = sum(1 for d in side_drafts if d.outcome == "pending")

                accept_rate = (accepted / total * 100) if total > 0 else 0
                reject_rate = (rejected / total * 100) if total > 0 else 0
                edit_rate = (edited / total * 100) if total > 0 else 0

                self._write_log(
                    f"[bold]Feedback Statistics:[/bold]\n"
                    f"  Total drafts: [cyan]{total}[/cyan]\n"
                    f"  Accepted: [green]{accepted}[/green] ({accept_rate:.1f}%)\n"
                    f"  Rejected: [red]{rejected}[/red] ({reject_rate:.1f}%)\n"
                    f"  Edited: [yellow]{edited}[/yellow] ({edit_rate:.1f}%)\n"
                    f"  Pending: [dim]{pending}[/dim]"
                )
            elif args == "clear":
                if typer.confirm("Clear all draft history? This cannot be undone."):
                    # Clear draft-history.jsonl
                    drafts_path = self._session.drafts_path
                    if drafts_path.exists():
                        drafts_path.unlink()
                        self._write_log("[green]✓ Draft history cleared[/green]")
                    else:
                        self._write_log("[dim]No draft history to clear[/dim]")
                else:
                    self._write_log("[dim]Cancelled[/dim]")
            else:
                # Show recent feedback examples
                rejected_edited = [
                    d for d in side_drafts[-10:]
                    if d.outcome in ("rejected", "edited")
                ]
                if rejected_edited:
                    self._write_log("[bold]Recent Feedback (last 10):[/bold]")
                    for d in rejected_edited:
                        snippet = d.content[:80] + "..." if len(d.content) > 80 else d.content
                        if d.outcome == "rejected":
                            self._write_log(f"  [red]❌ REJECTED:[/red] \"{snippet}\"")
                        elif d.outcome == "edited":
                            final = (d.final_content or "")[:80]
                            self._write_log(
                                f"  [yellow]✏️ EDITED:[/yellow] \"{snippet[:40]}...\" → \"{final}...\""
                            )
                else:
                    self._write_log("[dim]No rejected or edited drafts yet[/dim]")

        elif base_cmd == "/emotion":
            # Show emotion state (client only)
            if self._session.side != "client":
                self._write_log("[yellow]Emotion tracking is only available for client side[/yellow]")
            else:
                from empathy.agents.emotion_manager import EmotionStateManager

                emotion_manager = EmotionStateManager(
                    self._session.dialogue_dir, self._session.agent.model
                )
                current_state = emotion_manager.load_current()

                if not current_state:
                    self._write_log("[dim]No emotion state recorded yet[/dim]")
                else:
                    # Display current state
                    primary = current_state.get("primary_emotion", "neutral")
                    intensity = current_state.get("intensity", 5)
                    secondary = current_state.get("secondary_emotions", [])
                    triggers = current_state.get("triggers", [])
                    physical = current_state.get("physical_sensations", [])
                    thoughts = current_state.get("thoughts", "")
                    change = current_state.get("change_direction", "stable")
                    reasoning = current_state.get("reasoning", "")

                    # Color code intensity
                    if intensity >= 8:
                        color = "red"
                    elif intensity >= 6:
                        color = "yellow"
                    elif intensity >= 4:
                        color = "white"
                    else:
                        color = "green"

                    self._write_log(f"[bold]Current Emotion State:[/bold]")
                    self._write_log(
                        f"  Primary: [{color}]{primary} ({intensity}/10)[/{color}]"
                    )

                    if secondary:
                        self._write_log(f"  Secondary: [dim]{', '.join(secondary)}[/dim]")

                    if triggers:
                        self._write_log(f"  Triggers: [dim]{', '.join(triggers)}[/dim]")

                    if physical:
                        self._write_log(
                            f"  Physical: [dim]{', '.join(physical)}[/dim]"
                        )

                    if thoughts:
                        self._write_log(f"  Thoughts: [dim]\"{thoughts}\"[/dim]")

                    self._write_log(f"  Change: [dim]{change}[/dim]")

                    if reasoning:
                        self._write_log(f"  Reasoning: [dim]{reasoning}[/dim]")

                    # Show recent history if args == "history"
                    if args == "history":
                        history_path = emotion_manager.history_path
                        if history_path.exists():
                            import json

                            lines = history_path.read_text().strip().split("\n")
                            recent = lines[-5:]  # Last 5 states

                            self._write_log("\n[bold]Recent History:[/bold]")
                            for line in recent:
                                try:
                                    state = json.loads(line)
                                    turn = state.get("turn_number", "?")
                                    emotion = state.get("primary_emotion", "?")
                                    intensity = state.get("intensity", "?")
                                    self._write_log(
                                        f"  Turn {turn}: {emotion} ({intensity}/10)"
                                    )
                                except json.JSONDecodeError:
                                    pass
                        else:
                            self._write_log("[dim]No history available[/dim]")

        elif base_cmd == "/tools":
            # Show tool usage statistics
            drafts = self._session.get_draft_history()
            side_drafts = [d for d in drafts if d.speaker == self._session.side]

            # Count API calls and tokens
            total_calls = len([d for d in side_drafts if d.api_usage])
            total_input = sum(d.api_usage.get("input_tokens", 0) for d in side_drafts if d.api_usage)
            total_output = sum(d.api_usage.get("output_tokens", 0) for d in side_drafts if d.api_usage)
            total_cached = sum(d.api_usage.get("cached_tokens", 0) for d in side_drafts if d.api_usage)
            total_latency = sum(d.api_usage.get("latency_ms", 0) for d in side_drafts if d.api_usage)
            avg_latency = (total_latency / total_calls) if total_calls > 0 else 0

            self._write_log(
                f"[bold]Tool Usage Statistics:[/bold]\n"
                f"  Total API calls: [cyan]{total_calls}[/cyan]\n"
                f"  Input tokens: [cyan]{total_input:,}[/cyan]\n"
                f"  Output tokens: [cyan]{total_output:,}[/cyan]\n"
                f"  Cached tokens: [green]{total_cached:,}[/green]\n"
                f"  Avg latency: [dim]{avg_latency:.0f}ms[/dim]\n"
                f"  Total latency: [dim]{total_latency:,}ms[/dim]"
            )

        else:
            self._write_log(f"[red]Unknown command:[/red] {cmd}")

        return False, False

    def _process_instruction(
        self,
        instruction: str,
        active_skills: list[Skill] | None = None,
    ) -> None:
        """Generate a draft from the instruction and show inline confirm."""
        # Always-on skills are appended on every call; triggered skills are additive.
        always = [s for s in self._skills.values() if s.mode == "always"]
        all_skills = always + (active_skills or []) or None
        self._write_log(f"[dim]> {instruction}[/dim]")
        self._write_log("[dim]Generating draft...[/dim]")

        # Set UI logger for real-time tool call visualization
        try:
            log = self.query_one("#left-log", RichLog)
            self._session.agent.set_ui_logger(log)
        except (NoMatches, AttributeError):
            pass

        self.run_worker(self._generate_and_confirm(instruction, all_skills), exclusive=True)

    async def _generate_and_confirm(
        self,
        instruction: str,
        active_skills: list[Skill] | None = None,
    ) -> None:
        """Async worker: generate draft then show confirm."""
        try:
            result = await anyio.to_thread.run_sync(
                lambda: self._session.generate_draft(instruction, active_skills=active_skills)
            )
        except Exception as e:
            self._write_log(f"[red]Draft generation failed:[/red] {e}")
            return

        if isinstance(result, ClarificationMessage):
            self._write_log(
                f"[bold magenta]Agent needs clarification:[/bold magenta] {result.content}"
            )
            self._write_log("[dim]Refine your instruction and press Enter to try again.[/dim]")
            with contextlib.suppress(NoMatches):
                cmd_input = self.query_one("#cmd-input", CommandInput)
                cmd_input.value = instruction
                cmd_input.cursor_position = len(instruction)
                cmd_input.focus()
            return

        draft = result

        # Show API usage stats if available
        if hasattr(draft, "hook_annotations") and draft.hook_annotations:
            api_usage = draft.hook_annotations.get("api_usage")
            if api_usage:
                input_tokens = api_usage.get("input_tokens", 0)
                output_tokens = api_usage.get("output_tokens", 0)
                cached_tokens = api_usage.get("cached_tokens", 0)
                latency_ms = api_usage.get("latency_ms", 0)
                self._write_log(
                    f"[dim]   API: {input_tokens} in, {output_tokens} out, "
                    f"{cached_tokens} cached, {latency_ms}ms[/dim]"
                )

            # Show emotion change if available (client only)
            emotion_change = draft.hook_annotations.get("emotion_change")
            if emotion_change:
                self._display_emotion_change(emotion_change)

        self._write_log(f"[bold yellow]Draft ready:[/bold yellow] {draft.content}")

        confirm_event: asyncio.Event = asyncio.Event()
        confirm_result: dict[str, str] = {}

        def on_confirm(key: str) -> None:
            confirm_result["key"] = key
            confirm_event.set()
            with contextlib.suppress(NoMatches):
                self.query_one("#cmd-input", CommandInput).focus()

        try:
            confirm_widget = self.query_one("#confirm-widget", ConfirmWidget)
            confirm_widget.show_confirm(draft.content, on_confirm)
            confirm_widget.focus()
        except NoMatches:
            self._write_log("[red]Confirm widget not found[/red]")
            return

        await confirm_event.wait()
        key = confirm_result.get("key", "r")

        if key == "a":
            turn = await anyio.to_thread.run_sync(lambda: self._session.accept_draft(draft))
            self._write_log(f"[green]✓ Committed (accept):[/green] {turn.content}")
            self._refresh_transcript()

        elif key == "e":
            self._pending_edit_draft = draft
            self._enter_edit_mode(draft.content, is_human=False)

        elif key == "r":
            await anyio.to_thread.run_sync(lambda: self._session.reject_draft(draft))
            self._write_log("[dim]Draft rejected.[/dim]")

        elif key == "h":
            await anyio.to_thread.run_sync(lambda: self._session.reject_draft(draft))
            self._direct_human_mode = True
            self._enter_edit_mode("", is_human=True)

        elif key == "refine":
            await anyio.to_thread.run_sync(lambda: self._session.reject_draft(draft))
            self._write_log("[dim]Instruction returned for refinement.[/dim]")
            with contextlib.suppress(NoMatches):
                cmd_input = self.query_one("#cmd-input", CommandInput)
                cmd_input.value = instruction
                cmd_input.cursor_position = len(instruction)
                cmd_input.focus()

    def on_unmount(self) -> None:
        with contextlib.suppress(Exception):
            self._session.release_floor()
