from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeployOptions:
    timeout_sec: int = 600
    force: bool = False


class Deployer(ABC):
    @abstractmethod
    def plan(self) -> str: ...

    @abstractmethod
    def apply(self) -> None: ...


# Skeletons to implement later
class ComposeDeployer(Deployer):
    def __init__(self, service_name: str, compose_path: str, target: str, opts: DeployOptions):
        self.service_name = service_name
        self.compose_path = compose_path
        self.target = target
        self.opts = opts

    def plan(self) -> str:
        return f"Would run: docker compose -f {self.compose_path} pull && up -d on target {self.target}"

    def apply(self) -> None:
        # TODO: exec docker compose against remote DOCKER_HOST
        raise NotImplementedError("ComposeDeployer.apply not implemented")