from __future__ import annotations

from .logging import get_console
from .state import State


class Ctx:
    def __init__(self, config: str, state: str, json_out: bool, apply: bool):
        self.config = config
        self.state = state
        self.json_out = json_out
        self.apply = apply
        self.console = get_console()
        self.store = State(state)
        self.store.open()

    def close(self) -> None:
        self.store.close()
