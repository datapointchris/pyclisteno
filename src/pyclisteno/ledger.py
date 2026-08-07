"""Assignments already handed out, and the ones retired for good.

State, not cache. Deleting this file silently changes what a typed sequence
means, which is why it sits under XDG_STATE_HOME in a directory shared by every
tool and synced across the fleet — a sequence learned on one machine has to mean
the same thing on the next.

A node is keyed by its path joined with spaces, so `glue nightly run` names the
`run` under `nightly` under `glue` and the root is the empty string. The value is
that node's prefix *at its own level*, never a whole sequence: sequences are
built by concatenating one prefix per level, and storing the concatenation would
break every descendant the moment an ancestor's prefix changed.

`retired` is a list per path rather than a single value, because a path can shed
more than one prefix over its life — a pin added later, then changed again. Every
string a path has ever answered to stays reserved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field

from pyclisteno import paths
from pyclisteno.model import write_atomically

SCHEMA = 1


def key_of(path: list[str]) -> str:
    return ' '.join(path)


def parent_key_of(key: str) -> str:
    return key.rsplit(' ', 1)[0] if ' ' in key else ''


def name_of(key: str) -> str:
    return key.rsplit(' ', 1)[-1]


@dataclass
class Ledger:
    tool: str
    assignments: dict[str, str] = field(default_factory=dict)
    retired: dict[str, list[str]] = field(default_factory=dict)
    schema: int = SCHEMA

    def to_dict(self) -> dict:
        return {
            'schema': self.schema,
            'tool': self.tool,
            'assignments': self.assignments,
            'retired': self.retired,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Ledger:
        return cls(
            tool=data['tool'],
            assignments=dict(data['assignments']),
            retired={key: list(prefixes) for key, prefixes in data['retired'].items()},
            schema=data['schema'],
        )


def render_ledger(ledger: Ledger) -> str:
    return json.dumps(ledger.to_dict(), indent=2, sort_keys=True) + '\n'


def load_ledger(tool: str) -> Ledger:
    """A tool with no ledger yet starts empty rather than failing.

    First run is the common case, and it is indistinguishable from a ledger
    someone deleted — both mean every prefix is computed from scratch.
    """
    path = paths.ledger_path(tool)
    if not path.exists():
        return Ledger(tool=tool)
    return Ledger.from_dict(json.loads(path.read_text()))


def save_ledger(ledger: Ledger) -> None:
    write_atomically(paths.ledger_path(ledger.tool), render_ledger(ledger))
