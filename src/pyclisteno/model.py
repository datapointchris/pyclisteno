"""The exported grammar: the node schema, and the two files it serialises to.

The schema is the artifact the language ports agree on rather than an internal
detail of this one — the zsh suggestion strategy is written once and must read a
Go-produced dump and a Python-produced dump identically. Renaming a field here
is a change to goclisteno and bashclisteno too, which is what `SCHEMA` exists to
signal.

Two files rather than one because the shell reads the index on the keystroke
path. A TSV goes straight into an assoc array; parsing JSON in zsh would cost a
subprocess per keystroke, which is the rule .zshrc already states for the doshell
widgets. The JSON is for everything not on that path — regeneration, assignment,
help rendering.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyclisteno import paths

SCHEMA = 1

Kind = Literal['group', 'command']


@dataclass
class Node:
    """One command in the tree.

    `prefix` is left unset by the export and filled by assignment, so a freshly
    walked model round-trips through JSON with every prefix still null.
    """

    path: list[str]
    name: str
    kind: Kind
    use: str
    summary: str
    takes_argument: bool
    excluded: bool
    prefix: str | None
    children: list[Node]

    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'name': self.name,
            'kind': self.kind,
            'use': self.use,
            'summary': self.summary,
            'takes_argument': self.takes_argument,
            'excluded': self.excluded,
            'prefix': self.prefix,
            'children': [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Node:
        return cls(
            path=list(data['path']),
            name=data['name'],
            kind=data['kind'],
            use=data['use'],
            summary=data['summary'],
            takes_argument=data['takes_argument'],
            excluded=data['excluded'],
            prefix=data['prefix'],
            children=[cls.from_dict(child) for child in data['children']],
        )

    def descendants(self) -> Iterator[Node]:
        """Every node beneath this one, parents before children."""
        for child in self.children:
            yield child
            yield from child.descendants()


@dataclass
class Model:
    tool: str
    tool_version: str | None
    root: Node
    schema: int = SCHEMA

    def nodes(self) -> Iterator[Node]:
        yield self.root
        yield from self.root.descendants()

    def to_dict(self) -> dict:
        return {
            'schema': self.schema,
            'tool': self.tool,
            'tool_version': self.tool_version,
            'root': self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Model:
        return cls(
            tool=data['tool'],
            tool_version=data['tool_version'],
            root=Node.from_dict(data['root']),
            schema=data['schema'],
        )


def render_model(model: Model) -> str:
    return json.dumps(model.to_dict(), indent=2) + '\n'


def render_index(model: Model) -> str:
    """One line per assigned shortcut: prefix, the command to type, the summary.

    Column two omits the argument metavars that `use` carries, because the shell
    inserts this text into the buffer and a literal `<alias>` is not typeable.
    """
    lines = []
    for node in model.nodes():
        if node.prefix is None:
            continue
        lines.append(f'{node.prefix}\t{" ".join([model.tool, *node.path])}\t{node.summary}')
    return ''.join(f'{line}\n' for line in lines)


def write_atomically(path: Path, text: str) -> None:
    """The shell reads these while the tool may be rewriting them.

    A torn read is a wrong suggestion rather than a crash, which is worse — it
    looks like the library disagreeing with itself. `replace` is atomic within a
    filesystem, and the scratch file is a sibling to keep it on the same one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(f'{path.name}.new')
    scratch.write_text(text)
    scratch.replace(path)


def load_model(path: Path) -> Model:
    return Model.from_dict(json.loads(path.read_text()))


def export(model: Model) -> None:
    """Both cache files from one walk.

    Never one and then the other from separate passes: the index is a projection
    of the model, and two walks either side of a tool upgrade would publish a
    prefix for a command the model no longer contains.
    """
    write_atomically(paths.model_path(model.tool), render_model(model))
    write_atomically(paths.index_path(model.tool), render_index(model))
