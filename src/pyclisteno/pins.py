"""The user's hand-written prefix pins — read by us, never written by us.

Written by a human, so it is the one file here that is config rather than state
or cache, and it lives beside the tool's own config where a user would look for
it. The keys are node paths and the values are that node's prefix at its own
level, matching the ledger:

    [shortcuts]
    run = "ru"
    "glue nightly" = "ni"

Nothing in here raises. A tool that dies on a typo in an optional config file is
a tool this library broke, and the whole proposition is that a CLI behaves
identically with it attached. An unusable pin is dropped and the prefix is
computed as if it were absent — including a pin that is not a prefix of the
command's own name, which assignment rejects through the same validity rule as
everything else rather than through a special case.
"""

from __future__ import annotations

import tomllib

from pyclisteno import paths


def load_pins(tool: str) -> dict[str, str]:
    path = paths.pins_path(tool)
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
        return {}
    shortcuts = data.get('shortcuts')
    if not isinstance(shortcuts, dict):
        return {}
    return {str(key): value for key, value in shortcuts.items() if isinstance(value, str)}
