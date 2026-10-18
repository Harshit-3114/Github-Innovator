import sys
import time
import io
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from db.schema import init_db
from db.repository import get_recent_runs, get_forked_repos
from agents.graph import run_pipeline
from agents.code_indexer import build_code_graph
from agents.planner import generate_innovation_plan
from agents.code_writer import execute_plan
from agents.readme_gen import generate_readme
from agents.publisher import fork_and_clone, commit_and_push, cleanup
from core.github_client import GitHubClient
from core.models import RepoInfo, QualifiedRepo

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

log_dir = Path.home() / ".github-innovator" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "innovator.log", encoding="utf-8"),
    ],
)

init_db()

app = typer.Typer(name="innovator")
console = Console()


@app.command()
def run():
    """Run the full pipeline: discover → analyze → plan → implement → fork"""
    console.print("[bold]GitHub Innovation Fork Agent[/bold]")
    console.print("Pipeline: discover repos → analyze → plan → implement → fork → publish\n")

    result = run_pipeline()

    if result["status"] == "completed":
        fork_url = result.get("fork_url", "")
        console.print(f"\n[bold green]Pipeline completed[/bold green] (run #{result['run_id']})")
        console.print(f"  Discovered: {result['repos_discovered']} repos")
        console.print(f"  Qualified:  {result['repos_qualified']} repos")
        console.print(f"  Retries:    {result['retries']}")
        if fork_url:
            console.print(f"\n[bold cyan]Fork created:[/bold cyan] {fork_url}")
        else:
            console.print("\n[yellow]No fork created — no qualifying opportunity found.[/yellow]")
    else:
        console.print(f"\n[bold red]Pipeline failed:[/bold red] {result.get('error', 'Unknown error')}")
        raise typer.Exit(1)


@app.command()
def history(limit: int = 10):
    """Show recent pipeline runs"""
    rows = get_recent_runs(limit)

    if not rows:
        console.print("No runs yet.")
        return

    table = Table(title=f"Recent Runs (last {len(rows)})")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Discovered", justify="right")
    table.add_column("Qualified", justify="right")
    table.add_column("Forks", justify="right")
    table.add_column("Started")
    table.add_column("Error")

    for row in rows:
        status_style = "green" if row["status"] == "completed" else "red"
        table.add_row(
            str(row["id"]),
            f"[{status_style}]{row['status']}[/{status_style}]",
            str(row["repos_discovered"]),
            str(row["repos_qualified"]),
            str(row["forks_created"]),
            row["started_at"][:19] if row["started_at"] else "",
            (row["error"] or "")[:40],
        )
    console.print(table)


@app.command()
def retry(limit: int = 5):
    """Re-commit changes to previously forked repos"""
    forked = get_forked_repos(limit)
    if not forked:
        console.print("[yellow]No forked repos found in DB.[/yellow]")
        return

    console.print(f"[bold]Re-committing to {len(forked)} forked repo(s)...[/bold]\n")
    gh = GitHubClient()
    success = 0

    for entry in forked:
        full_name = entry["full_name"]
        fork_url = entry.get("fork_url", "")
        console.print(f"[cyan]>>> {full_name}[/cyan]")

        fork_name = full_name.split("/")[1] + "-ai"
        result = fork_and_clone(gh, full_name)
        if not result:
            console.print("  [red]Failed to clone fork[/red]")
            continue
        repo_path, _ = result

        repo_info = RepoInfo(full_name=full_name, owner=full_name.split("/")[0], name=full_name.split("/")[1],
                             description="", language="Python", stars=0, topics=[], license_key="",
                             pushed_at="", clone_url="", size_bytes=0)
        qualified = QualifiedRepo(repo=repo_info, score=10, rationale="Retry", best_innovation="",
                                  difficulty=1, estimated_effort_hours=1)

        code_graph = build_code_graph(repo_path, "Python")
        plan = generate_innovation_plan(qualified, code_graph)
        if not plan or not plan.changes:
            console.print("  [yellow]No changes generated, skipping[/yellow]")
            cleanup(repo_path)
            continue

        changes = execute_plan(qualified, plan, code_graph, repo_path)
        if not changes:
            console.print("  [yellow]No changes implemented, skipping[/yellow]")
            cleanup(repo_path)
            continue

        readme = generate_readme(qualified, plan, fork_name)
        result_url = commit_and_push(repo_path, plan, fork_url, readme_content=readme)
        cleanup(repo_path)

        if result_url and "/tree/" in result_url:
            console.print(f"  [green]Pushed: {result_url}[/green]")
            success += 1
        else:
            console.print("  [red]Push failed[/red]")

    console.print(f"\n[bold]Done. {success}/{len(forked)} repos updated.[/bold]")


@app.command()
def tui():
    """Launch the interactive TUI dashboard"""
    from tui.app import main as tui_main
    tui_main()


@app.command()
def daemon(interval_hours: int = 6):
    """Run the pipeline continuously every N hours"""
    console.print(f"[bold]Starting daemon mode[/bold] (every {interval_hours} hours)")
    console.print("Press Ctrl+C to stop\n")
    try:
        while True:
            console.print("[bold]=== Starting pipeline run ===[/bold]")
            result = run_pipeline()
            status = result["status"]
            icon = "[green]OK[/green]" if status == "completed" else "[red]FAIL[/red]"
            fork = result.get("fork_url", "no fork")
            console.print(f"{icon} Run #{result['run_id']} — {fork}")
            console.print(f"[dim]Next run in {interval_hours} hours...[/dim]\n")
            time.sleep(interval_hours * 3600)
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon stopped.[/yellow]")


if __name__ == "__main__":
    app()
