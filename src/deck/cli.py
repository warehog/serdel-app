from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table
from rich import box

from .logging import get_console, setup_logging
from .state import State
from .config import load_service_spec, list_services
from .providers.deploy import ComposeDeployer, DeployOptions
from .providers.backup import ResticBackup
from .providers.targets import load_inventory, check_target, endpoint_for

app = typer.Typer(add_completion=False, help="Deploy, backup and migrate containerized services")


class Ctx:
    def __init__(self, config: str, state: str, json_out: bool, apply: bool):
        self.config = config
        self.state = state
        self.json_out = json_out
        self.apply = apply
        self.console = get_console()
        self.store = State(state)
        self.store.open()

    def close(self):
        self.store.close()


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option("./deck.yaml", help="Path to global config file"),
    state: str = typer.Option("./state.db", help="Path to state database (sqlite)"),
    json_out: bool = typer.Option(False, "--json", help="JSON output where supported"),
    apply: bool = typer.Option(False, "--apply", help="Execute actions (otherwise dry-run)"),
):
    """Global options & setup."""
    setup_logging()
    ctx.obj = Ctx(config, state, json_out, apply)


@app.command()
def status(
    ctx: typer.Context,
    service: Optional[str] = typer.Argument(None, help="Service name or omit to list all"),
):
    """Show service or fleet status (skeleton)."""
    c: Ctx = ctx.obj
    if not service:
        names = list_services()
        if c.json_out:
            typer.echo(json.dumps({"services": names}))
            return
        table = Table(title="Services", box=box.SIMPLE)
        table.add_column("Name", style="bold")
        for n in names:
            table.add_row(n)
        c.console.print(table)
        return

    sp = load_service_spec(service)
    out = {
        "service": sp.metadata.name,
        "desiredTarget": sp.spec.deployment.target,
        "method": sp.spec.deployment.method,
        "healthy": None,
    }
    if c.json_out:
        typer.echo(json.dumps(out, indent=2))
    else:
        c.console.print(f"[bold]Service[/]: {out['service']}")
        c.console.print(f"Target:  {out['desiredTarget']}")
        c.console.print(f"Method:  {out['method']}")
        c.console.print("Healthy: unknown")


@app.command()
def deploy(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    target: Optional[str] = typer.Option(None, help="Override destination target"),
    timeout: int = typer.Option(600, help="Wait timeout in seconds"),
    force: bool = typer.Option(False, help="Force redeploy even if no changes detected"),
):
    """Deploy or update a service to its target (skeleton)."""
    c: Ctx = ctx.obj
    sp = load_service_spec(service)
    tgt = target or sp.spec.deployment.target

    plan = ""
    if sp.spec.deployment.method == "compose":
        cp = sp.compose_path
        plan = ComposeDeployer(sp.metadata.name, str(cp), tgt, DeployOptions(timeout, force)).plan()
    else:
        plan = f"Would deploy {sp.metadata.name} via {sp.spec.deployment.method} to {tgt}"

    mode = "apply" if c.apply else "plan"
    c.console.print(f"[{mode}] {plan}")
    c.store.event(service=sp.metadata.name, command="deploy", mode=mode, payload={"target": tgt})

    if c.apply:
        # TODO: call real provider .apply()
        pass


@app.command()
def backup(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    now: bool = typer.Option(False, "--now", help="Run a backup immediately"),
    verify: bool = typer.Option(False, help="Verify repository integrity"),
    list_: bool = typer.Option(False, "--list", help="List snapshots/archives"),
    prune: bool = typer.Option(False, help="Prune old snapshots per retention"),
):
    """Run or manage backups for a service (skeleton)."""
    c: Ctx = ctx.obj
    sp = load_service_spec(service)
    b = ResticBackup(service=sp.metadata.name, repo=sp.spec.storage.backup.repository)

    mode = "apply" if c.apply else "plan"
    c.console.print(f"[{mode}] backup {sp.metadata.name} (now={now} verify={verify} list={list_} prune={prune}) via {sp.spec.storage.backup.driver}")
    c.console.print(b.plan())
    c.store.event(service=sp.metadata.name, command="backup", mode=mode, payload={"now": now, "verify": verify, "list": list_, "prune": prune})


@app.command()
def migrate(
    ctx: typer.Context,
    service: str = typer.Argument(..., help="Service name"),
    to: str = typer.Option(..., "--to", help="Destination target name"),
    via: str = typer.Option("auto", help="Strategy: auto|rsync|restic|snapshot"),
    downtime_seconds: int = typer.Option(30, help="Expected downtime window during cutover"),
):
    """Migrate a service's data & workload to another target (skeleton)."""
    c: Ctx = ctx.obj
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    msg = f"[{mode}] would migrate {sp.metadata.name} from {sp.spec.deployment.target} to {to} via {via} (downtime≈{downtime_seconds}s)"
    c.console.print(msg)
    c.store.event(service=sp.metadata.name, command="migrate", mode=mode, payload={"to": to, "via": via, "downtime": downtime_seconds})


@app.command()
def start(ctx: typer.Context, service: str = typer.Argument(..., help="Service name")):
    """Start (resume) a service (skeleton)."""
    c: Ctx = ctx.obj
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    c.console.print(f"[{mode}] would start {sp.metadata.name} via {sp.spec.deployment.method}")
    c.store.event(service=sp.metadata.name, command="start", mode=mode, payload={})


@app.command()
def stop(ctx: typer.Context, service: str = typer.Argument(..., help="Service name")):
    """Stop (quiesce) a service (skeleton)."""
    c: Ctx = ctx.obj
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    c.console.print(f"[{mode}] would stop {sp.metadata.name} via {sp.spec.deployment.method}")
    c.store.event(service=sp.metadata.name, command="stop", mode=mode, payload={})


@app.command("targets")
def list_targets(
    ctx: typer.Context,
    check: bool = typer.Option(False, "--check", help="Probe each target for reachability"),
    inventory: Optional[str] = typer.Option(None, "--inventory", help="Path to targets/inventory.yaml (defaults to ./targets/inventory.yaml)"),
):
    """List all targets; optionally check connectivity."""
    c: Ctx = ctx.obj
    inv_path = Path(inventory) if inventory else None
    targets = load_inventory(inv_path)

    if c.json_out:
        if check:
            results = []
            for t in targets:
                r = check_target(t)
                results.append(
                    {
                        "name": r.name,
                        "type": r.type,
                        "endpoint": r.endpoint,
                        "reachable": r.reachable,
                        "latency_ms": r.latency_ms,
                        "detail": r.detail,
                    }
                )
            typer.echo(json.dumps({"targets": results}, indent=2))
        else:
            typer.echo(
                json.dumps(
                    {
                        "targets": [
                            {"name": t.name, "type": t.type, "endpoint": endpoint_for(t)} for t in targets
                        ]
                    },
                    indent=2,
                )
            )
        return

    title = "Targets (checked)" if check else "Targets"
    table = Table(title=title, box=box.SIMPLE)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Endpoint")
    if check:
        table.add_column("Reachable")
        table.add_column("Latency ms")
        table.add_column("Detail")

    for t in targets:
        ep = endpoint_for(t)
        if check:
            r = check_target(t)
            table.add_row(
                r.name,
                r.type,
                r.endpoint,
                "✅" if r.reachable else "❌",
                f"{r.latency_ms:.1f}" if r.latency_ms is not None else "-",
                r.detail,
            )
        else:
            table.add_row(t.name, t.type, ep)

    c.console.print(table)
