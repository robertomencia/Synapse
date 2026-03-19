"""Synapse CLI — control interface."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="synapse",
    help="◈ Synapse — AI Reality Layer",
    add_completion=False,
)
console = Console()


@app.command()
def start(
    no_hud: bool = typer.Option(False, "--no-hud", help="Disable the overlay HUD"),
) -> None:
    """Start Synapse — begin watching, learning, acting."""
    console.print("[bold cyan]◈ Synapse[/] starting up...", highlight=False)
    from synapse.main import main
    main(hud=not no_hud)


@app.command()
def status() -> None:
    """Show current Synapse status and recent activity."""
    console.print("[bold cyan]◈ Synapse Status[/]")

    from synapse.config import settings
    from synapse.memory.memory_manager import MemoryManager

    memory = MemoryManager(settings.chroma_path, settings.sqlite_path)
    memory.connect()

    recent = asyncio.run(memory.get_recent(minutes=60))

    table = Table(title="Recent Activity (last 60 min)")
    table.add_column("Time", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Text", no_wrap=False)

    for entry in recent[:20]:
        table.add_row(
            entry.timestamp.strftime("%H:%M:%S"),
            entry.source,
            entry.text[:80],
        )

    console.print(table)
    console.print(f"\nTotal observations in memory: [bold]{memory.total_observations}[/]")
    memory.close()


@app.command()
def query(
    q: str = typer.Argument(..., help="Natural language query (e.g. 'what was I working on yesterday?')"),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of results"),
) -> None:
    """Query Synapse's memory semantically."""
    from synapse.config import settings
    from synapse.memory.memory_manager import MemoryManager

    memory = MemoryManager(settings.chroma_path, settings.sqlite_path)
    memory.connect()

    results = asyncio.run(memory.search_semantic(q, limit=limit))

    console.print(f"\n[bold cyan]◈ Memory query:[/] {q}\n")
    for i, entry in enumerate(results, 1):
        console.print(f"[dim]{i}.[/] [{entry.source}] {entry.text}")
        console.print(f"   [dim]{entry.timestamp.strftime('%Y-%m-%d %H:%M')} · relevance: {entry.relevance_score:.2f}[/]\n")

    if not results:
        console.print("[dim]No relevant memories found.[/]")

    memory.close()


@app.command()
def reset_memory(
    confirm: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Wipe all Synapse memory (irreversible)."""
    if not confirm:
        typer.confirm("This will delete ALL Synapse memory. Are you sure?", abort=True)

    import shutil
    from synapse.config import settings

    if settings.chroma_path.exists():
        shutil.rmtree(settings.chroma_path)
    if settings.sqlite_path.exists():
        settings.sqlite_path.unlink()

    console.print("[green]Memory wiped.[/] Synapse starts fresh next time.")


if __name__ == "__main__":
    app()
