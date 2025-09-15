from rich.console import Console
from rich.theme import Theme
import logging

_console = Console(theme=Theme({"info": "cyan", "warn": "yellow", "error": "bold red"}))


def get_console() -> Console:
    return _console


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )