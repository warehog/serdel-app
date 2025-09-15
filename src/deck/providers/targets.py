from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import socket
import ssl
import time
import subprocess
import urllib.parse
import yaml


@dataclass
class Target:
    name: str
    type: str  # docker|kubernetes|ssh
    connection: Dict[str, str]


@dataclass
class TargetCheckResult:
    name: str
    type: str
    endpoint: str
    reachable: bool
    latency_ms: Optional[float]
    detail: str


DEFAULT_INVENTORY_PATH = Path("targets") / "inventory.yaml"


def load_inventory(path: Optional[Path] = None) -> List[Target]:
    """Load targets from YAML inventory."""
    inv_path = path or DEFAULT_INVENTORY_PATH
    if not inv_path.exists():
        return []
    data = yaml.safe_load(inv_path.read_text()) or {}
    items = data.get("targets", [])
    out: List[Target] = []
    for it in items:
        out.append(Target(name=it.get("name"), type=it.get("type"), connection=it.get("connection", {})))
    return out


def endpoint_for(t: Target) -> str:
    c = t.connection or {}
    if t.type == "docker":
        return c.get("dockerHost", "tcp://localhost:2375")
    if t.type == "kubernetes":
        ctx = c.get("context", "")
        kube = c.get("kubeconfig", "~/.kube/config")
        return f"{ctx}@{kube}" if ctx else kube
    if t.type == "ssh":
        user = c.get("user", "")
        host = c.get("host", "")
        port = c.get("port", "22")
        at = f"{user}@" if user else ""
        return f"{at}{host}:{port}"
    return ""


def check_target(t: Target, timeout: float = 5.0) -> TargetCheckResult:
    if t.type == "docker":
        ok, detail, ms = _check_docker(t.connection, timeout)
        return TargetCheckResult(t.name, t.type, endpoint_for(t), ok, ms, detail)
    if t.type == "kubernetes":
        ok, detail, ms = _check_k8s(t.connection, timeout)
        return TargetCheckResult(t.name, t.type, endpoint_for(t), ok, ms, detail)
    if t.type == "ssh":
        ok, detail, ms = _check_ssh(t.connection, timeout)
        return TargetCheckResult(t.name, t.type, endpoint_for(t), ok, ms, detail)
    return TargetCheckResult(t.name, t.type, endpoint_for(t), False, None, "unknown target type")


def _check_docker(conn: Dict[str, str], timeout: float) -> Tuple[bool, str, Optional[float]]:
    host_url = conn.get("dockerHost", "tcp://127.0.0.1:2375")
    parsed = urllib.parse.urlparse(host_url)
    if parsed.scheme not in ("tcp", "http", "https"):
        return False, f"unsupported scheme: {parsed.scheme}", None
    host = parsed.hostname or "127.0.0.1"
    tls_flag = str(conn.get("tls", "false")).lower() == "true" or parsed.scheme == "https"
    port = parsed.port or (2376 if tls_flag else 2375)
    start = time.time()
    try:
        raw = socket.create_connection((host, port), timeout=timeout)
        s = raw
        if tls_flag:
            ctx = ssl.create_default_context()
            if str(conn.get("insecure", "false")).lower() == "true":
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(raw, server_hostname=host)
        # Docker Engine API ping
        s.sendall(b"GET /_ping HTTP/1.0\r\n\r\n")
        data = s.recv(128)
        s.close()
        ms = (time.time() - start) * 1000.0
        ok = b"OK" in data or b"200" in data
        return ok, ("pong" if ok else f"unexpected: {data[:32]!r}"), ms
    except Exception as e:  # noqa: BLE001
        return False, str(e), None


def _check_k8s(conn: Dict[str, str], timeout: float) -> Tuple[bool, str, Optional[float]]:
    kubeconfig = conn.get("kubeconfig")
    context = conn.get("context")
    cmd = ["kubectl"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]
    if context:
        cmd += ["--context", context]
    cmd += ["version", "--short", f"--request-timeout={int(timeout)}s"]
    start = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        ms = (time.time() - start) * 1000.0
        if p.returncode == 0:
            return True, (p.stdout.strip().splitlines()[0] if p.stdout else "ok"), ms
        return False, (p.stderr.strip() or p.stdout.strip()), None
    except FileNotFoundError:
        return False, "kubectl not found in PATH", None
    except subprocess.TimeoutExpired:
        return False, "kubectl timed out", None
    except Exception as e:  # noqa: BLE001
        return False, str(e), None


def _check_ssh(conn: Dict[str, str], timeout: float) -> Tuple[bool, str, Optional[float]]:
    host = conn.get("host")
    if not host:
        return False, "missing host", None
    user = conn.get("user")
    port = str(conn.get("port", 22))
    key = conn.get("keyPath")
    dest = f"{user}@{host}" if user else host
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        f"ConnectTimeout={int(timeout)}",
        "-p",
        str(port),
    ]
    if key:
        cmd += ["-i", key]
    cmd += [dest, "true"]
    start = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        ms = (time.time() - start) * 1000.0
        if p.returncode == 0:
            return True, "ok", ms
        return False, (p.stderr.strip() or p.stdout.strip()), None
    except FileNotFoundError:
        # Fall back to TCP check on port 22
        try:
            port_i = int(port)
            s = socket.create_connection((host, port_i), timeout=timeout)
            s.close()
            return True, "tcp-connect", None
        except Exception as e2:  # noqa: BLE001
            return False, f"ssh not found; tcp failed: {e2}", None
    except subprocess.TimeoutExpired:
        return False, "ssh timed out", None
    except Exception as e:  # noqa: BLE001
        return False, str(e), None