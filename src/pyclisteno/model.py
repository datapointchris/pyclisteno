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
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Literal

from pyclisteno import paths
from pyclisteno.markup import strip_markup

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

    # In-process only, and deliberately not part of the schema: a `@shortcut`
    # pin is an *input* to assignment, and the dump records what assignment
    # decided. `excluded` has to be serialised because a null prefix alone
    # cannot say whether a node was kept off the fast path or simply had no
    # valid prefix left; a pin needs no such witness, because the prefix it
    # produced is right there. Excluded from equality so a walked model still
    # round-trips through JSON unchanged.
    pin: str | None = field(default=None, compare=False)

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


def sequences(model: Model) -> list[tuple[Node, str]]:
    """Every reachable node and the single token that types it.

    The sequence is every ancestor's prefix followed by the node's own, run
    together with no separator: `exgsr`, not `ex g s r`. One stroke rather than
    four words is the whole point of the analogy the library is named for, and
    it is what the design settled on before the spaces crept in.

    A node under an unassigned parent is unreachable however short its own prefix
    is, so the walk stops rather than producing a sequence nothing can type.
    """
    found: list[tuple[Node, str]] = []

    def descend(node: Node, sequence: str) -> None:
        for child in node.children:
            if child.prefix is None:
                continue
            typed = sequence + child.prefix
            found.append((child, typed))
            descend(child, typed)

    descend(model.root, '')
    return found


def unambiguous_sequences(model: Model) -> list[tuple[Node, str]]:
    """Sequences no other command also answers to.

    Running the prefixes together loses the level boundaries, so a string can
    parse more than one way — and any string that does is, by construction, the
    concatenation of two different paths. A duplicate is therefore the whole test,
    and a sequence that fails it is published by nobody rather than silently won
    by whichever command sorted first.

    Names are held back too. A root command called `env` must not be swallowed by
    some deeper path that happens to run together as `env`, because the token a
    user typed is a real command and the CLI can answer it itself.
    """
    found = sequences(model)
    seen = Counter(typed for _, typed in found)
    names = {child.name for child in model.root.children}
    return [(node, typed) for node, typed in found if seen[typed] == 1 and typed not in names]


def index_rows(model: Model) -> list[tuple[str, str, str]]:
    """The typed sequence, the command it stands for, and the summary.

    Column two omits the argument metavars that `use` carries, because the shell
    inserts this text into the buffer and a literal `<alias>` is not typeable.
    Column three loses its rich tags for the same reason — see markup.py.
    """
    return [(typed, ' '.join([model.tool, *node.path]), strip_markup(node.summary)) for node, typed in unambiguous_sequences(model)]


def render_index(model: Model) -> str:
    return ''.join(f'{typed}\t{command}\t{summary}\n' for typed, command, summary in index_rows(model))


def write_atomically(path: Path, text: str) -> None:
    """The shell reads these while the tool may be rewriting them.

    A torn read is a wrong suggestion rather than a crash, which is worse — it
    looks like the library disagreeing with itself. `replace` is atomic within a
    filesystem, and the scratch file is a sibling to keep it on the same one.

    Unchanged content is not rewritten, which is what `attach` relies on instead
    of a staleness check: the rendered text *is* the fingerprint, so there is
    nothing to store, nothing to compare it against, and no way for the stored
    one to disagree with the file it describes. It matters because the ledger is
    synced — an identical rewrite still moves the mtime, and every invocation of
    every tool would wake Syncthing for nothing.
    """
    if path.exists() and path.read_text() == text:
        return
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
