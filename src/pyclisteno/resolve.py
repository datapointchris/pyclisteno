"""Expanding a typed sequence back into the full command.

The walk goes one token at a time. A token equal to a child's full name reaches
that child before any prefix is tried, so a real command name always reaches its
command. Otherwise the longest match wins: a token matches a child when it starts
with the child's prefix and is itself a prefix of the child's name.

**Retired sequences are dead ends, and resolution has to know about them.**
Assignment stops a *new* prefix from capturing a retired string, but it cannot
undo an assignment that already existed: with `review` holding `r` and `runs`
later retired at `ru`, typing `ru` would fall through to the live `r` and run
review. The fix is not to lengthen review's prefix — that breaks a sequence
someone is using today to protect one nobody can use at all — but to let the
retired string win its own longest match and stop. Typing it reports that the
command is gone, which is the whole point of never recycling.

**The first token is tried as a whole sequence before the walk.** With `jobs`
holding `j` and its `run` holding `ru`, `jru` reaches `jobs run` in one step. A
first token that is a sequence ends resolution there, and every token after it
is handed back as typed. So `j ru` reaches `jobs` and hands back `ru`: the
prefixes of one sequence are typed together. The walk runs when the first token
is not a sequence, as when it is a full name. `jobs ru nightly` reaches
`jobs run` and hands back `nightly`.

Tokens resolution cannot consume are handed back rather than swallowed.
Everything after the last command is that command's arguments, which is what lets
a caller expand `jru nightly` without knowing where the grammar ends and the
argument begins.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from pyclisteno.ledger import Ledger
from pyclisteno.ledger import key_of
from pyclisteno.ledger import parent_key_of
from pyclisteno.model import Model
from pyclisteno.model import Node
from pyclisteno.model import unambiguous_sequences


@dataclass(frozen=True)
class Resolution:
    node: Node
    remainder: list[str]
    retired: str | None = None


def retired_at(ledger: Ledger, parent_key: str) -> list[str]:
    retired = []
    for key, prefixes in ledger.retired.items():
        if parent_key_of(key) == parent_key:
            retired.extend(prefixes)
    return retired


def named_child(node: Node, token: str) -> Node | None:
    """The child whose full name is the token, prefix or none.

    Tried before any prefix, because a real command name has to reach that
    command. An incumbent keeps its prefix when a sibling arrives, so with `runs`
    holding `ru`, a `run` added later gets no prefix. `run` starts with `ru`, so
    prefix matching alone would answer `run` with `runs`. argparse resolves an
    abbreviated option in the same order: exact match first, then prefix.
    """
    return next((child for child in node.children if child.name == token), None)


def match_child(node: Node, token: str) -> Node | None:
    """Both bounds are needed. `update --help` passed as one argument starts with `update`'s prefix and is not `update`."""
    longest = None
    for child in node.children:
        if child.prefix is None or not token.startswith(child.prefix) or not child.name.startswith(token):
            continue
        if longest is None or len(child.prefix) > len(str(longest.prefix)):
            longest = child
    return longest


def match_retired(retired: list[str], token: str) -> str | None:
    matches = [prefix for prefix in retired if token.startswith(prefix)]
    return max(matches, key=len) if matches else None


def sequence_index(model: Model) -> dict[str, Node]:
    return {typed: node for node, typed in unambiguous_sequences(model)}


def resolve(model: Model, tokens: list[str], ledger: Ledger | None = None) -> Resolution:
    """The deepest node the tokens reach, and whatever is left over.

    The whole sequence in one token is tried first, and it has to be: `exgsr`
    also starts with `ex`, so the per-token walk below would happily answer it
    with `example-pipeline` and drop the rest on the floor.

    The walk still runs for everything else, and it is what makes the long form
    work: a token equal to a child's full name reaches that child before any
    prefix is tried. A sequence that matches nothing
    resolves to the root with everything left over, which is the caller's signal
    that it expanded no further. Passing no ledger resolves against live prefixes
    alone, correct for a tool that has never retired anything.
    """
    if tokens:
        whole = sequence_index(model).get(tokens[0])
        if whole is not None:
            return Resolution(node=whole, remainder=tokens[1:])
    node = model.root
    for index, token in enumerate(tokens):
        named = named_child(node, token)
        if named is not None:
            node = named
            continue
        child = match_child(node, token)
        retired = match_retired(retired_at(ledger, key_of(node.path)), token) if ledger else None
        if retired is not None and (child is None or len(retired) > len(str(child.prefix))):
            return Resolution(node=node, remainder=tokens[index:], retired=retired)
        if child is None:
            return Resolution(node=node, remainder=tokens[index:])
        node = child
    return Resolution(node=node, remainder=[])


def expand(model: Model, tokens: list[str], ledger: Ledger | None = None) -> list[str]:
    """The typed sequence as the command it stands for, arguments intact."""
    resolution = resolve(model, tokens, ledger)
    return [model.tool, *resolution.node.path, *resolution.remainder]


def expand_argv(model: Model, ledger: Ledger | None = None, argv: list[str] | None = None) -> bool:
    """Rewrite a typed sequence in place, before the CLI parses it. True if anything changed.

    Conservative by construction, because this is the one surface that can make a
    CLI run a command its user did not type:

    - A sequence that reaches nothing is left alone, so an unknown token produces
      the CLI's own error rather than a truncated command. A token that runs past
      a command's name reaches nothing, so `"update --help"` quoted into one
      argument is not run as `update`.
    - A retired sequence is left alone for the same reason. Expanding to the node
      reached *before* it would run an ancestor of a command that no longer
      exists, which is the silent wrong answer retirement exists to prevent.
    - A leading option stops the walk at the first token, so `--env prod` and
      anything like it passes through untouched rather than being reinterpreted.

    A real command name expands to itself, because resolution tries a child's
    full name before any prefix. That holds for a command assignment left
    without a prefix, and it is what keeps this from shadowing anything.
    """
    argv = sys.argv if argv is None else argv
    tokens = argv[1:]
    if not tokens:
        return False
    # Enrollment happens at import, and an import is not always a run: pytest
    # collecting a module that calls `attach` would otherwise have its own
    # arguments rewritten, and so would anything else importing the CLI. The
    # program has to actually be the tool before its argv is anyone's business.
    if Path(argv[0]).name != model.tool:
        return False
    resolution = resolve(model, tokens, ledger)
    if resolution.retired is not None or not resolution.node.path:
        return False
    expanded = [*resolution.node.path, *resolution.remainder]
    if expanded == tokens:
        return False
    argv[1:] = expanded
    return True
