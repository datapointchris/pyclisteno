"""Enrollment: the one call a CLI makes, and the one it deletes to drop this.

`attach(app)` after the tree is complete, rather than a decorator per command,
because a tree assembled at runtime from config has no functions to decorate —
which is the case that motivated the library, not an edge of it.

**Nothing here may raise.** The library's whole proposition is that a CLI behaves
identically with it attached, and a tool that dies because a cache directory is
read-only or a ledger got truncated is a tool this library broke. Every failure
is swallowed and enrollment is skipped; set CLISTENO_DEBUG to get the traceback
instead, because a failure nobody can see is its own kind of broken.

There is no staleness check. Assignment is pure computation over a tree already
in memory, so recomputing it costs less than deciding whether to, and the two
cache files and the ledger are only rewritten when their rendered content
actually differs. See `write_atomically`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pyclisteno.assign import assign
from pyclisteno.ledger import load_ledger
from pyclisteno.ledger import save_ledger
from pyclisteno.model import Model
from pyclisteno.model import export
from pyclisteno.pins import load_pins
from pyclisteno.resolve import expand_argv
from pyclisteno.teach import teach
from pyclisteno.walk import CommandLike
from pyclisteno.walk import as_command
from pyclisteno.walk import walk

DEBUG_VARIABLE = 'CLISTENO_DEBUG'


def infer_tool(command: CommandLike) -> str:
    """What the user types, which is not always what the app calls itself.

    A typer app built without a name converts to a command with none, so the
    fallback is the invoked script — the same string the shell integration sees.
    """
    return command.name or Path(sys.argv[0]).name


def enroll(app: object, tool: str | None, version: str | None, teaching: bool, expanding: bool) -> Model:
    command = as_command(app)
    name = tool or infer_tool(command)
    pins = load_pins(name)
    model = walk(command, name, version)
    ledger = assign(model, load_ledger(name), pins)
    save_ledger(ledger)
    export(model)
    if expanding:
        expand_argv(model, ledger)
    if teaching:
        # The app, not the converted command: a typer tree is rebuilt on every
        # conversion, so what runs is never the object the walk just read.
        teach(app, model)
    return model


def attach(
    app: object, tool: str | None = None, version: str | None = None, teaching: bool = False, expanding: bool = False
) -> Model | None:
    """Walk, assign, publish. Returns the assigned model, or None if anything went wrong.

    `teaching` is the one argument that changes what the CLI prints, and
    `expanding` the one that changes what it runs. Both are off by default, so
    adopting the library commits to neither.
    """
    try:
        return enroll(app, tool, version, teaching, expanding)
    except Exception:
        if os.environ.get(DEBUG_VARIABLE):
            raise
        return None
