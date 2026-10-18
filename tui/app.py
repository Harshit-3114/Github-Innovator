import logging
import queue
import threading
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.reactive import var
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Select, Static

from agents.graph import run_pipeline
from core.llm_client import nim
from db.repository import get_recent_runs
from db.schema import init_db

log_queue: queue.Queue = queue.Queue()


class TuiLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        log_queue.put(msg)


class StatsPanel(Static):
    discovered = var(0)
    qualified = var(0)
    forks = var(0)

    def render(self) -> str:
        return (
            " ┌─────────────┬─────────────┬─────────────┐\n"
            " │  Discovered  │  Qualified   │   Forks     │\n"
            " ├─────────────┼─────────────┼─────────────┤\n"
            f" │    {self.discovered:>5}     │    {self.qualified:>5}     │    {self.forks:>5}     │\n"
            " └─────────────┴─────────────┴─────────────┘"
        )


class Dashboard(Screen):
    CSS = """
    Screen {
        background: $surface;
    }
    #main-container {
        padding: 1 2;
        height: 100%;
    }
    StatsPanel {
        width: 100%;
        height: 5;
        margin: 0 0 1 0;
    }
    #status-bar {
        height: 1;
        margin: 0 0 1 0;
    }
    #status-label {
        width: 100%;
        text-style: bold;
    }
    #log {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    #button-bar {
        height: 3;
        align: center middle;
        margin: 0 0 0 0;
    }
    Button {
        margin: 0 1;
        min-width: 18;
    }
    #run-btn {
        background: $success;
    }
    #history-btn {
        background: $primary;
    }
    #quit-btn {
        background: $error;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            StatsPanel(id="stats"),
            Horizontal(
                Label("Status: [yellow]Idle[/]", id="status-label"),
                id="status-bar",
            ),
            RichLog(id="log", highlight=True, markup=True, wrap=True, max_lines=500),
            Horizontal(
                Button("▶ Run Pipeline", id="run-btn", variant="success"),
                Button("📋 History", id="history-btn", variant="primary"),
                Button("✕ Quit", id="quit-btn", variant="error"),
                id="button-bar",
            ),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.15, self.poll_logs)
        self.set_interval(5, self.refresh_stats)
        self.refresh_stats()

    async def poll_logs(self) -> None:
        log = self.query_one("#log", RichLog)
        lines = []
        while not log_queue.empty():
            try:
                lines.append(log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            log.write("\n".join(lines))

    def refresh_stats(self) -> None:
        try:
            rows = get_recent_runs(1)
            if rows:
                row = rows[0]
                stats = self.query_one("#stats", StatsPanel)
                stats.discovered = row["repos_discovered"] or 0
                stats.qualified = row["repos_qualified"] or 0
                stats.forks = row["forks_created"] or 0
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "run-btn":
            self.app.push_screen("count_prompt")
        elif btn_id == "history-btn":
            self.app.push_screen("history")
        elif btn_id == "quit-btn":
            self.app.exit()

    @staticmethod
    def _capture_run(max_repos: int = 0, model: str | None = None) -> dict[str, Any]:
        try:
            result = run_pipeline(max_repos=max_repos, model=model)
            log_queue.put("\n[bold green]✓ Pipeline complete[/bold green]")
            fork_url = result.get("fork_url", "")
            if fork_url:
                log_queue.put(f"  Fork: {fork_url}")
            log_queue.put(f"  Discovered: {result.get('repos_discovered', 0)}  "
                           f"Qualified: {result.get('repos_qualified', 0)}  "
                           f"Retries: {result.get('retries', 0)}")
            return result
        except Exception as e:
            log_queue.put(f"\n[bold red]✗ Pipeline failed: {e}[/bold red]")
            return {}

    def _pipeline_done(self, _future: threading.Thread) -> None:
        status = self.query_one("#status-label", Label)
        status.update("Status: [yellow]Idle[/]")
        btn = self.query_one("#run-btn", Button)
        btn.disabled = False
        btn.label = "▶ Run Pipeline"
        self.refresh_stats()

    def run_pipeline(self, max_repos: int = 0, model: str | None = None) -> None:
        status = self.query_one("#status-label", Label)
        status.update("Status: [green]Running...[/]")
        btn = self.query_one("#run-btn", Button)
        btn.disabled = True
        btn.label = "⏳ Running..."
        if max_repos:
            log_queue.put(f"\n[bold]Starting run — forking up to {max_repos} repo(s)[/bold]")
        if model:
            log_queue.put(f"[bold]Using model: {model}[/bold]")

        def worker() -> None:
            self._capture_run(max_repos, model)
            self.app.call_from_thread(self._pipeline_done, threading.current_thread())

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


class CountPromptScreen(Screen):
    CSS = """
    #prompt-container {
        align: center middle;
        height: 100%;
    }
    #prompt-box {
        width: 50;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }
    #prompt-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #repo-input {
        margin-top: 1;
        margin-bottom: 1;
    }
    #prompt-actions {
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Label("How many repos to fork?", id="prompt-title"),
                Label("Enter 0 to fork all qualified repos.", id="prompt-hint"),
                Input(placeholder="e.g. 3", id="repo-input", type="integer"),
                Horizontal(
                    Button("Run", id="confirm-btn", variant="success"),
                    Button("Cancel", id="cancel-btn", variant="error"),
                    id="prompt-actions",
                ),
                id="prompt-box",
            ),
            id="prompt-container",
        )

    def on_mount(self) -> None:
        self.query_one("#repo-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._confirm(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self._confirm(self.query_one("#repo-input", Input).value)
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()

    def _confirm(self, value: str) -> None:
        try:
            count = int(value.strip() or "0")
        except ValueError:
            count = 0
        self.app._pending_repo_count = count
        self.app.pop_screen()
        self.app.push_screen("model_prompt")


class ModelPromptScreen(Screen):
    CSS = """
    #model-container {
        align: center middle;
        height: 100%;
    }
    #model-box {
        width: 70;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }
    #model-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #model-select {
        margin-top: 1;
        margin-bottom: 1;
    }
    #model-actions {
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._models: list[str] = []

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Label("Select LLM model:", id="model-title"),
                Label("Fetching available models from NVIDIA NIM...", id="model-hint"),
                Select(
                    [("Loading...", "")],
                    id="model-select",
                    allow_blank=False,
                ),
                Horizontal(
                    Button("Run", id="model-confirm-btn", variant="success"),
                    Button("Cancel", id="model-cancel-btn", variant="error"),
                    id="model-actions",
                ),
                id="model-box",
            ),
            id="model-container",
        )

    def on_mount(self) -> None:
        self.set_loading(True)
        thread = threading.Thread(target=self._load_models, daemon=True)
        thread.start()

    def _load_models(self) -> None:
        models = nim.list_models()
        if not models:
            models = [nim.model]
        self._models = models
        self.app.call_from_thread(self._populate)

    def _populate(self) -> None:
        self.set_loading(False)
        select = self.query_one("#model-select", Select)
        options = [(m, m) for m in self._models]
        if nim.model not in self._models:
            options = [(f"{nim.model} (default)", nim.model)] + options
        select.set_options(options)
        select.value = nim.model
        select.focus()

    def set_loading(self, loading: bool) -> None:
        self.query_one("#model-hint", Label).update(
            "Fetching available models from NVIDIA NIM..." if loading
            else f"{len(self._models)} model(s) available"
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value:
            self.query_one("#model-hint", Label).update(f"Selected: {event.value}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "model-confirm-btn":
            self._confirm()
        elif event.button.id == "model-cancel-btn":
            self.app.pop_screen()

    def _confirm(self) -> None:
        select = self.query_one("#model-select", Select)
        model = str(select.value or nim.model)
        self.app.pop_screen()
        dashboard = self.app.screen
        if isinstance(dashboard, Dashboard):
            count = getattr(self.app, "_pending_repo_count", 0)
            dashboard.run_pipeline(max_repos=count, model=model)


class HistoryScreen(Screen):
    CSS = """
    Screen {
        background: $surface;
    }
    #history-container {
        padding: 1 2;
        height: 100%;
    }
    DataTable {
        height: 1fr;
        border: solid $primary;
        margin: 0 0 1 0;
    }
    Button {
        min-width: 18;
    }
    #back-bar {
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Label("[bold]Run History[/bold]", id="history-title"),
            DataTable(id="history-table"),
            Horizontal(
                Button("← Back", id="back-btn", variant="primary"),
                Button("⟳ Refresh", id="refresh-btn"),
                id="back-bar",
            ),
            id="history-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("ID", "Status", "Discovered", "Qualified", "Forks", "Started", "Error")
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.clear()
        try:
            rows = get_recent_runs(50)
            for row in rows:
                status = row["status"]
                status_display = {
                    "completed": "[green]completed[/]",
                    "failed": "[red]failed[/]",
                    "running": "[yellow]running[/]",
                }.get(status, status)
                table.add_row(
                    str(row["id"]),
                    status_display,
                    str(row["repos_discovered"] or 0),
                    str(row["repos_qualified"] or 0),
                    str(row["forks_created"] or 0),
                    (row["started_at"] or "")[:19],
                    (row["error"] or "")[:40],
                )
        except Exception as e:
            table.add_row("--", f"[red]{e}[/]", "--", "--", "--", "--", "--")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back-btn":
            self.app.pop_screen()
        elif event.button.id == "refresh-btn":
            self.refresh_table()


class InnovatorTUI(App[None]):
    TITLE = "GitHub Innovator"
    SUB_TITLE = "AI-Powered Repository Forking Agent"

    _pending_repo_count: int = 0

    SCREENS = {
        "history": HistoryScreen,
        "count_prompt": CountPromptScreen,
        "model_prompt": ModelPromptScreen,
    }

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("h", "push_screen('history')", "History"),
        Binding("r", "run_pipeline", "Run"),
    ]

    def on_mount(self) -> None:
        self.push_screen(Dashboard())

    def action_run_pipeline(self) -> None:
        screen = self.screen
        if isinstance(screen, Dashboard):
            self.push_screen("count_prompt")


def main() -> None:
    init_db()

    handler = TuiLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    app = InnovatorTUI()
    app.run()


if __name__ == "__main__":
    main()
