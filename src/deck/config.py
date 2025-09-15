from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import yaml
from pathlib import Path


class HealthCheck(BaseModel):
    type: str = "http"
    url: Optional[str] = None
    timeoutSeconds: int = 10
    retries: int = 6


class DeploymentSource(BaseModel):
    path: Optional[str] = None
    values: Optional[str] = None


class Deployment(BaseModel):
    method: str  # compose|k8s|helm|ssh
    source: DeploymentSource = Field(default_factory=DeploymentSource)
    target: str
    strategy: Dict[str, object] | None = None


class Volume(BaseModel):
    name: str
    mountPath: str
    kind: str  # hostPath|dockerVolume|pvc


class BackupCfg(BaseModel):
    driver: str = "restic"
    schedule: Optional[str] = None
    includes: List[str] = Field(default_factory=list)
    excludes: List[str] = Field(default_factory=list)
    repository: Optional[str] = None
    credentialsRef: Optional[str] = None


class Storage(BaseModel):
    volumes: List[Volume] = Field(default_factory=list)
    backup: BackupCfg = Field(default_factory=BackupCfg)


class Spec(BaseModel):
    deployment: Deployment
    storage: Storage = Field(default_factory=Storage)


class Metadata(BaseModel):
    name: str
    labels: Dict[str, str] = Field(default_factory=dict)


class ServiceSpec(BaseModel):
    apiVersion: str
    kind: str
    metadata: Metadata
    spec: Spec

    def validate_basic(self) -> None:
        if not self.metadata.name:
            raise ValueError("metadata.name is required")
        if not self.spec.deployment.method:
            raise ValueError("spec.deployment.method is required")

    @property
    def root_dir(self) -> Path:
        return Path("services") / self.metadata.name

    @property
    def compose_path(self) -> Optional[Path]:
        p = self.spec.deployment.source.path
        return (self.root_dir / p) if p else None


def load_service_spec(name: str) -> ServiceSpec:
    path = Path("services") / name / "service.yaml"
    data = yaml.safe_load(path.read_text())
    spec = ServiceSpec.model_validate(data)
    if not spec.metadata.name:
        spec.metadata.name = name
    spec.validate_basic()
    return spec


def list_services() -> list[str]:
    base = Path("services")
    if not base.exists():
        return []
    out = []
    for d in base.iterdir():
        if (d / "service.yaml").exists():
            out.append(d.name)
    return sorted(out)