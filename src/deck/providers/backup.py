from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


class BackupProvider(ABC):
    @abstractmethod
    def plan(self) -> str: ...

    @abstractmethod
    def run_now(self) -> None: ...

    @abstractmethod
    def list(self) -> None: ...

    @abstractmethod
    def verify(self) -> None: ...

    @abstractmethod
    def prune(self) -> None: ...


@dataclass
class ResticBackup(BackupProvider):
    service: str
    repo: str | None

    def plan(self) -> str:
        return f"Would restic backup to {self.repo or '<unset repo>'}"

    def run_now(self) -> None:
        raise NotImplementedError

    def list(self) -> None:
        raise NotImplementedError

    def verify(self) -> None:
        raise NotImplementedError

    def prune(self) -> None:
        raise NotImplementedError