from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich import box
from rich.table import Table

from .context import Ctx
from .config import load_service_spec, list_services
from .providers.backup import ResticBackup
from .providers.deploy import ComposeDeployer, DeployOptions
from .providers.targets import check_target, endpoint_for, load_inventory


def status(c: Ctx, service: Optional[str]) -> None:
    """Show service or fleet status."""
    if not service:
        names = list_services()
        if c.json_out:
            print(json.dumps({"services": names}))
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
        print(json.dumps(out, indent=2))
    else:
        c.console.print(f"[bold]Service[/]: {out['service']}")
        c.console.print(f"Target:  {out['desiredTarget']}")
        c.console.print(f"Method:  {out['method']}")
        c.console.print("Healthy: unknown")


def deploy(
    c: Ctx, service: str, target: Optional[str], timeout: int, force: bool
) -> None:
    """Deploy or update a service to its target."""
    sp = load_service_spec(service)
    tgt = target or sp.spec.deployment.target

    if sp.spec.deployment.method == "compose":
        cp = sp.compose_path
        plan = ComposeDeployer(
            sp.metadata.name, str(cp), tgt, DeployOptions(timeout, force)
        ).plan()
    else:
        plan = (
            f"Would deploy {sp.metadata.name} via {sp.spec.deployment.method} to {tgt}"
        )

    mode = "apply" if c.apply else "plan"
    c.console.print(f"[{mode}] {plan}")
    c.store.event(
        service=sp.metadata.name, command="deploy", mode=mode, payload={"target": tgt}
    )

    if c.apply:
        # TODO: call real provider .apply()
        pass


def backup(
    c: Ctx,
    service: str,
    now: bool,
    verify: bool,
    list_: bool,
    prune: bool,
) -> None:
    """Run or manage backups for a service."""
    sp = load_service_spec(service)
    b = ResticBackup(service=sp.metadata.name, repo=sp.spec.storage.backup.repository)

    mode = "apply" if c.apply else "plan"
    c.console.print(
        f"[{mode}] backup {sp.metadata.name} (now={now} verify={verify} list={list_} prune={prune}) "
        f"via {sp.spec.storage.backup.driver}"
    )
    c.console.print(b.plan())
    c.store.event(
        service=sp.metadata.name,
        command="backup",
        mode=mode,
        payload={"now": now, "verify": verify, "list": list_, "prune": prune},
    )


def migrate(
    c: Ctx,
    service: str,
    to: str,
    via: str,
    downtime_seconds: int,
) -> None:
    """Migrate a service's data & workload to another target."""
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    msg = (
        f"[{mode}] would migrate {sp.metadata.name} from {sp.spec.deployment.target} "
        f"to {to} via {via} (downtime≈{downtime_seconds}s)"
    )
    c.console.print(msg)
    c.store.event(
        service=sp.metadata.name,
        command="migrate",
        mode=mode,
        payload={"to": to, "via": via, "downtime": downtime_seconds},
    )


def start(c: Ctx, service: str) -> None:
    """Start (resume) a service."""
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    c.console.print(
        f"[{mode}] would start {sp.metadata.name} via {sp.spec.deployment.method}"
    )
    c.store.event(service=sp.metadata.name, command="start", mode=mode, payload={})


def stop(c: Ctx, service: str) -> None:
    """Stop (quiesce) a service."""
    sp = load_service_spec(service)
    mode = "apply" if c.apply else "plan"
    c.console.print(
        f"[{mode}] would stop {sp.metadata.name} via {sp.spec.deployment.method}"
    )
    c.store.event(service=sp.metadata.name, command="stop", mode=mode, payload={})


def list_targets(c: Ctx, check: bool, inventory: Optional[str]) -> None:
    """List all targets; optionally check connectivity."""
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
            print(json.dumps({"targets": results}, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "targets": [
                            {
                                "name": t.name,
                                "type": t.type,
                                "endpoint": endpoint_for(t),
                            }
                            for t in targets
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
