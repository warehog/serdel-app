from __future__ import annotations

from typing import Optional

import typer

from .context import Ctx
from .logging import setup_logging
from . import commands

app = typer.Typer(
    add_completion=False, help="Deploy, backup and migrate containerized services"
)


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option("./deck.yaml", help="Path to global config file"),
    state: str = typer.Option("./state.db", help="Path to state database (sqlite)"),
    json_out: bool = typer.Option(False, "--json", help="JSON output where supported"),
    apply: bool = typer.Option(
        False, "--apply", help="Execute actions (otherwise dry-run)"
    ),
) -> None:
    """Global options & setup."""
    setup_logging()
    ctx.obj = Ctx(config, state, json_out, apply)


@app.command()
def status(
    ctx: typer.Context,
    service: Optional[str] = typer.Argument(
        None, help="Service name or omit to list all"
    ),
) -> None:
    """Show service or fleet status."""
    commands.status(ctx.obj, service)


@app.command()
def deploy(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    target: Optional[str] = typer.Option(None, help="Override destination target"),
    timeout: int = typer.Option(600, help="Wait timeout in seconds"),
    force: bool = typer.Option(
        False, help="Force redeploy even if no changes detected"
    ),
) -> None:
    """Deploy or update a service to its target."""
    commands.deploy(ctx.obj, service, target, timeout, force)


@app.command()
def backup(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    now: bool = typer.Option(False, "--now", help="Run a backup immediately"),
    verify: bool = typer.Option(False, help="Verify repository integrity"),
    list_: bool = typer.Option(False, "--list", help="List snapshots/archives"),
    prune: bool = typer.Option(False, help="Prune old snapshots per retention"),
) -> None:
    """Run or manage backups for a service."""
    commands.backup(ctx.obj, service, now, verify, list_, prune)


@app.command()
def migrate(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    to: str = typer.Option(..., "--to", help="Destination target name"),
    via: str = typer.Option("auto", help="Strategy: auto|rsync|restic|snapshot"),
    downtime_seconds: int = typer.Option(
        30, help="Expected downtime window during cutover"
    ),
) -> None:
    """Migrate a service's data & workload to another target."""
    commands.migrate(ctx.obj, service, to, via, downtime_seconds)


@app.command()
def start(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
) -> None:
    """Start (resume) a service."""
    commands.start(ctx.obj, service)


@app.command()
def stop(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
) -> None:
    """Stop (quiesce) a service."""
    commands.stop(ctx.obj, service)


@app.command("targets")
def list_targets(
    ctx: typer.Context,
    check: bool = typer.Option(
        False, "--check", help="Probe each target for reachability"
    ),
    inventory: Optional[str] = typer.Option(
        None,
        "--inventory",
        help="Path to targets/inventory.yaml (defaults to ./targets/inventory.yaml)",
    ),
) -> None:
    """List all targets; optionally check connectivity."""
    commands.list_targets(ctx.obj, check, inventory)
