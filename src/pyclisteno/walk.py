"""Command tree to grammar model.

**The walk is structural, and imports neither click nor typer.** Typer used to
build its tree out of click's own objects, which is why an `isinstance` check
against `click.Command` once covered both. It no longer does: typer 0.27 vendors
a complete copy of click at `typer._click`, whose `Command` derives from `ABC`
and shares no base class with the installed click. Anything matching on class
identity sees a typer tree as "not a command at all" and returns an empty model,
which is a silent wrong answer rather than a crash.

What the two implementations do agree on is shape, exactly:

- a command has `name`, `help`, `short_help`, `hidden`, `callback`, `params`
- only a group has `list_commands` and `get_command`
- a parameter reports `param_type_name` as `argument` or `option`
- a command names its own `context_class`, so each implementation supplies the
  context its own `list_commands` expects

That shape is the real interface, so it is what `CommandLike` states and what the
ports implement against. Matching on it costs the library its last runtime
dependency and survives the next time either project rearranges its classes.

The walk reads and returns a value. It never mutates a command, which is what
makes the non-invasiveness property testable rather than hoped for.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from typing import runtime_checkable

from pyclisteno.marks import is_excluded
from pyclisteno.marks import pinned_prefix
from pyclisteno.model import Model
from pyclisteno.model import Node

try:
    from typer.main import get_command

    convert_typer_app: Callable[..., object] | None = get_command
except ImportError:
    # typer is not a dependency and does not need to be: an app that needs
    # converting is itself proof that whoever passed it has typer installed.
    convert_typer_app = None


@runtime_checkable
class CommandLike(Protocol):
    name: str | None
    help: str | None
    short_help: str | None
    hidden: bool
    callback: Callable | None
    params: list
    context_class: type


class ParameterLike(Protocol):
    name: str | None
    param_type_name: str
    required: bool
    nargs: int


@runtime_checkable
class TyperAppLike(Protocol):
    registered_commands: list
    registered_groups: list


def as_command(app: object) -> CommandLike:
    if isinstance(app, CommandLike):
        return app
    # Checked before converting rather than letting typer fail: `get_command`
    # reaches straight for a private attribute, so anything else arrives as an
    # AttributeError naming typer's internals instead of the caller's mistake.
    if not isinstance(app, TyperAppLike):
        raise TypeError(f'cannot walk {type(app).__name__}: expected a command tree or a typer app')
    if convert_typer_app is None:
        raise TypeError(f'cannot walk {type(app).__name__}: it looks like a typer app, but typer is not installed to convert it')
    converted = convert_typer_app(app)
    if not isinstance(converted, CommandLike):
        raise TypeError(f'cannot walk {type(app).__name__}: typer converted it to {type(converted).__name__}, which is not a command')
    return converted


def is_group(command: CommandLike) -> bool:
    return hasattr(command, 'list_commands') and hasattr(command, 'get_command')


def arguments_of(command: CommandLike) -> list[ParameterLike]:
    return [param for param in command.params if param.param_type_name == 'argument']


def summarize(command: CommandLike) -> str:
    """First paragraph, whitespace collapsed, never truncated.

    Click's `get_short_help_str` truncates to 45 characters and typer's zsh
    completion to 50, which is where the trailing ellipsis in every completion
    menu comes from. A consumer that needs it shorter can cut it; nothing
    downstream can recover what was cut here.

    The backspace is click's own no-rewrap marker, which reads as a stray control
    character once the paragraph is collapsed onto one line.
    """
    text = command.short_help or (command.help or '').split('\n\n')[0]
    return ' '.join(text.replace('\x08', '').split())


def format_argument(argument: ParameterLike) -> str:
    """Angle brackets for required, square for optional — cli-design.md's help-row convention."""
    label = str(argument.name).replace('_', '-')
    if argument.nargs == -1:
        return f'<{label}>...'
    if argument.required:
        return f'<{label}>'
    return f'[{label}]'


def build_node(command: CommandLike, name: str, path: list[str], tool: str) -> Node:
    """A context per node, because a group may generate its children on demand.

    `list_commands` and `get_command` both take one, and a tree built from config
    is exactly the case that cannot answer without it. The context is built from
    the command's own `context_class` and given no parent: the parent chain only
    feeds usage strings, which nothing here reads, and a mixed tree would
    otherwise hand one implementation's context to the other's group.
    """
    context = command.context_class(command, info_name=name)
    arguments = arguments_of(command)
    children = []
    if is_group(command):
        # Sorted, because the model is a spec artifact and assignment reads
        # siblings in order to decide who keeps a contested prefix. Click sorts
        # its commands and typer preserves declaration order, so an unsorted walk
        # would hand the same tree different shortcuts depending on which library
        # built it — and goclisteno a third set again.
        for child_name in sorted(command.list_commands(context)):  # type: ignore[attr-defined]
            child = command.get_command(context, child_name)  # type: ignore[attr-defined]
            # A hidden command is not part of the grammar anyone learns, and
            # letting one consume a prefix would push a visible sibling onto a
            # longer one for the sake of a command that never appears in help.
            if child is None or child.hidden:
                continue
            children.append(build_node(child, child_name, [*path, child_name], tool))
    return Node(
        path=path,
        name=name,
        kind='group' if is_group(command) else 'command',
        use=' '.join([tool, *path, *(format_argument(argument) for argument in arguments)]),
        summary=summarize(command),
        takes_argument=bool(arguments),
        excluded=is_excluded(command.callback),
        prefix=None,
        children=children,
        pin=pinned_prefix(command.callback),
    )


def walk(app: object, tool: str, version: str | None = None) -> Model:
    """Walk a finished command tree into a model, prefixes unassigned."""
    return Model(tool=tool, tool_version=version, root=build_node(as_command(app), tool, [], tool))


def commands_by_path(app: object) -> dict[str, CommandLike]:
    """Every live command, keyed the way the model keys its nodes.

    A second traversal rather than a reference to each command hung off its node:
    a Node is a serialisable record of the grammar, and putting a live object on
    one makes the thing that gets written to disk own the thing that cannot be.
    Only teaching needs the commands themselves, and only while the process runs.
    """
    found: dict[str, CommandLike] = {}

    def descend(command: CommandLike, name: str, path: list[str]) -> None:
        found[' '.join(path)] = command
        if not is_group(command):
            return
        context = command.context_class(command, info_name=name)
        for child_name in sorted(command.list_commands(context)):  # type: ignore[attr-defined]
            child = command.get_command(context, child_name)  # type: ignore[attr-defined]
            if child is not None:
                descend(child, child_name, [*path, child_name])

    root = as_command(app)
    descend(root, root.name or '', [])
    return found
