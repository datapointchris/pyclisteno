"""Every path the library reads or writes, and the class each one belongs to.

Four paths across three XDG bases, and the nesting is deliberately not uniform:
the config file is namespaced by tool, while state and cache are namespaced by
library. That inversion is load-bearing rather than cosmetic.

The config file sits in the tool's own directory because that is where a user
looks for a tool's settings, and it sits *beside* the tool's config rather than
inside it — nothing here is ever merged into a file the tool parses, so a tool
never has to know this library exists and dropping the library leaves no orphan
keys behind.

State and cache invert it because `~/.local/state/<tool>/` is not ours. Tools
using pyselfupdate keep `autoupdate.json` there, recording the version installed
on *this* machine, which must never be replicated. The ledger must be, or the
same typed sequence resolves differently on different machines. One shared
directory keeps those two requirements from colliding and means adopting the
library costs no new synced folder.
"""

from __future__ import annotations

import os
from pathlib import Path

LIBRARY = 'clisteno'

CONFIG_SUFFIX = f'{LIBRARY}-shortcuts.toml'


def _base(env_var: str, *fallback: str) -> Path:
    override = os.environ.get(env_var)
    return Path(override).expanduser() if override else Path.home().joinpath(*fallback)


def config_home() -> Path:
    return _base('XDG_CONFIG_HOME', '.config')


def state_home() -> Path:
    return _base('XDG_STATE_HOME', '.local', 'state')


def cache_home() -> Path:
    return _base('XDG_CACHE_HOME', '.cache')


def pins_path(tool: str) -> Path:
    """The user's hand-written prefix pins. Written by a human, read by us, never the reverse."""
    return config_home() / tool / CONFIG_SUFFIX


def ledger_path(tool: str) -> Path:
    """Assignments already handed out. Deleting it silently changes what a typed sequence means."""
    return state_home() / LIBRARY / f'{tool}.json'


def model_path(tool: str) -> Path:
    """The walked command tree."""
    return cache_home() / LIBRARY / f'{tool}.json'


def index_path(tool: str) -> Path:
    """Flat prefix index for the shell.

    Separate from the model, and a different format, because the suggestion
    strategy runs on the keystroke path where parsing JSON is not affordable.
    """
    return cache_home() / LIBRARY / f'{tool}.tsv'
