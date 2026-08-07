"""Showing the short form beside the long one, so ordinary use trains the fast path.

Opt-in, and the only surface here that deliberately changes what a CLI prints —
which is why it is an argument rather than something `attach` does by default.
With it off, enrollment is byte-identical; with it on, that is the point.

**It writes `short_help`, not the renderer.** The row a parent's help shows for
each child comes from that string, so setting it is enough and no help formatter,
template or rich style is touched. That matters beyond tidiness: cli-design.md
settles that Python help is rich's with rich's defaults, and a library patching
the renderer would make every tool adopting it the odd one, which is the exact
objection that settled the rule.

**Where it writes depends on who built the tree, and getting this wrong is
silent.** A click app's commands are the objects that run, so writing to them
works. A typer app's do not exist yet: `get_command` builds a fresh tree on every
call, so a mutation applied to a converted command is discarded the moment typer
converts again to actually run. The durable target is typer's own `CommandInfo`
and `TyperInfo`, which is where the built tree reads `short_help` from. Both
expose that attribute under the same name, so only the lookup differs.

The names are derived through typer's own `get_command_name` rather than by
reimplementing its rules, and `test_every_assigned_node_has_somewhere_to_write`
fails loudly if the derivation ever stops matching the walked tree — the failure
mode being taught rows that silently stop appearing.

Writing `short_help` replaces what the row would otherwise derive from `help`.
The summary already *is* that first paragraph, collapsed, so the row keeps its
text and gains the hint — with one edge: where the renderer would have shortened
a derived string to fit, an explicit one is used whole and wraps instead. Neither
click nor rich does that at ordinary terminal widths, so it is a narrow-terminal
difference rather than the general improvement it first looks like.

Cockburn's novice-to-expert survey is why this surface is not the point of the
library: displaying a shortcut beside the slow path mostly does *not* produce
transition. What produces it is a fast path structurally identical to the slow
one, which is what prefix assignment is for. This is the reminder, not the
mechanism.
"""

from __future__ import annotations

from pyclisteno.ledger import key_of
from pyclisteno.model import Model
from pyclisteno.walk import TyperAppLike
from pyclisteno.walk import commands_by_path

try:
    from typer.main import get_command_name
except ImportError:
    get_command_name = None  # type: ignore[assignment]


def hint(prefix: str, summary: str) -> str:
    """Parentheses rather than square brackets, which the help rows already use for optional arguments."""
    return f'({prefix}) {summary}'


def group_name(info: object) -> str | None:
    """A sub-app names itself in `add_typer`, in its own info, or through its callback."""
    for candidate in (info.name, info.typer_instance.info.name):  # type: ignore[attr-defined]
        if candidate:
            return candidate
    callback = info.typer_instance.info.callback  # type: ignore[attr-defined]
    return get_command_name(callback.__name__) if callback and get_command_name is not None else None


def typer_targets(app: object) -> dict[str, object]:
    """Path key to the typer info whose `short_help` feeds that row."""
    targets: dict[str, object] = {}

    def descend(instance: object, path: list[str]) -> None:
        for info in instance.registered_commands:  # type: ignore[attr-defined]
            name = info.name or (get_command_name(info.callback.__name__) if get_command_name is not None else None)
            if name:
                targets[' '.join([*path, name])] = info
        for info in instance.registered_groups:  # type: ignore[attr-defined]
            name = group_name(info)
            if not name:
                continue
            targets[' '.join([*path, name])] = info
            descend(info.typer_instance, [*path, name])

    descend(app, [])
    return targets


def targets_for(app: object) -> dict[str, object]:
    if isinstance(app, TyperAppLike):
        return typer_targets(app)
    return dict(commands_by_path(app))


def teach(app: object, model: Model) -> None:
    """Write each assigned node's short form into the row its parent renders."""
    targets = targets_for(app)
    for node in model.nodes():
        target = targets.get(key_of(node.path))
        if node.prefix is None or target is None:
            continue
        target.short_help = hint(node.prefix, node.summary)  # type: ignore[attr-defined]
