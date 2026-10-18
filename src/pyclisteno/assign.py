"""Minimal unambiguous prefix, grandfathered, resolved by longest match.

A prefix is a literal prefix of the command's own name, so the short form is the
long form with less of it typed and there is no second vocabulary to learn. One
prefix per level; a sequence is the concatenation.

**The invariant.** Resolution takes the typed token and picks the longest
assigned prefix that the token starts with, among the siblings whose name the
token is a prefix of. For that to be correct, everything a
user might type on the way from a node's prefix to its full name has to land on
that node, which reduces to one rule over any two live siblings A and B:

    if prefix(A) is a prefix of name(B), then len(prefix(A)) <= len(prefix(B))

Every condition in `is_valid` is that rule, plus the reservation of strings
already spoken for. It is also why `run` and `runs` cannot both be short: with
`run` holding `r`, `runs` may take neither `ru` nor `run`, because typing `run`
would then reach `runs`. It takes its own full name, and typing `run` still
reaches `run` through the shorter `r`.

The invariant says what is *correct*; `choose_prefix` says what is *chosen*, and
prefers a prefix no sibling name shares. The two differ on `review` beside `run`:
handing the bare `r` to whichever sorts first is valid but wrong, because a user
typing `r` there has said something genuinely ambiguous and deserves nothing
rather than a coin toss.

**Retired prefixes are reserved differently from live ones**, and the asymmetry
is the point rather than an oversight. A retired command cannot be reached, so
nothing can steal its territory and no live node has to keep off its name. What
it does keep is its string: no node may be issued that exact prefix, and no node
may take a prefix short enough that the retired string falls through to it —
retire `ru`, assign `r` to a new `run`, and a sequence still in someone's fingers
quietly runs something else.

Those two conditions cover every prefix assigned from here on, but they cannot
reach backwards. A prefix handed out before the retirement can still capture the
retired string, and the answer is not to take it off the incumbent — that breaks
a sequence in use today to protect one nobody can use at all. Resolution carries
the other half by letting a retired string win its own longest match and stop
there. See the module docstring in resolve.py.

**Precedence**: a pin in the user's config, then `@shortcut` in the source, then
the ledger's grandfather, then the computed minimum. A lock that is not valid
where it lands falls through to the next source rather than displacing anything.

**Every prefix the ledger records at a level is reserved for its own path**,
whether that path holds it or retired it. So a pin moves only its own command. A
pin naming a prefix a sibling holds is not valid, and falls through like any
other lock. The reservation also covers a command removed in the same run that a
sibling arrives. Its prefix is retired when the run ends, and nothing may take it
first.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyclisteno.ledger import Ledger
from pyclisteno.ledger import key_of
from pyclisteno.ledger import name_of
from pyclisteno.ledger import parent_key_of
from pyclisteno.model import Model
from pyclisteno.model import Node


@dataclass(frozen=True)
class Claim:
    """One prefix already spoken for within a sibling set."""

    key: str
    name: str
    prefix: str
    live: bool


def is_valid(candidate: str, name: str, claims: list[Claim]) -> bool:
    """Whether `candidate` can be this node's prefix without breaking the invariant.

    A candidate that is not a prefix of the node's own name fails here, which is
    how a bad pin gets dropped without a special case for it.
    """
    if not candidate or not name.startswith(candidate):
        return False
    for claim in claims:
        if claim.prefix == candidate:
            return False
        if claim.live and claim.name.startswith(candidate) and len(candidate) > len(claim.prefix):
            return False
        if name.startswith(claim.prefix) and len(claim.prefix) > len(candidate):
            return False
    return True


def candidates_of(name: str) -> list[str]:
    return [name[:length] for length in range(1, len(name) + 1)]


def choose_prefix(name: str, sibling_names: list[str], claims: list[Claim]) -> str | None:
    """The shortest prefix that is unambiguous among the sibling names, then valid.

    Unambiguity comes first and is what makes `review` and `run` into `re` and
    `ru` rather than letting whichever sorts first take the bare `r`. A user
    typing `r` there has said something genuinely ambiguous, and answering it
    with whichever command happened to be assigned earlier is a worse outcome
    than answering it with nothing.

    The fallback exists for the one case where no unambiguous prefix can exist:
    `run` beside `runs`, where every prefix of `run` is also a prefix of `runs`.
    It takes the bare `r`, and `runs` — which does have an unambiguous prefix in
    its own full name — takes that. Typing `run` still reaches `run`, through the
    shorter match.

    Returning None rather than raising: an unlucky ledger must cost a command its
    fast path, never the CLI its startup.
    """
    others = [other for other in sibling_names if other != name]
    unambiguous = [candidate for candidate in candidates_of(name) if not any(other.startswith(candidate) for other in others)]
    for candidate in [*unambiguous, *candidates_of(name)]:
        if is_valid(candidate, name, claims):
            return candidate
    return None


def strands_a_sibling(pin: str, name: str, sibling_names: list[str]) -> bool:
    """Whether a pin would leave a sibling no prefix, so that typing its name reaches this node.

    A sibling whose name starts with the pin and is itself a prefix of this name
    can only take a prefix that is also a prefix of this name, and the invariant
    caps every such prefix at the pin's length. With `runs` pinned to `ru`, `run`
    has nothing left, and typing `run` reaches `runs`. `is_valid` catches this
    for a sibling already assigned. A pin is checked before the free siblings are
    assigned, so it needs this check for the rest.
    """
    return any(other != name and other.startswith(pin) and name.startswith(other) for other in sibling_names)


def locks_for(node: Node, key: str, pins: dict[str, str], ledger: Ledger, sibling_names: list[str]) -> list[str]:
    """Candidate prefixes in precedence order, highest first.

    The ledger's own retired entry for this key is a candidate too — reissuing a
    prefix to the command that held it is the opposite of recycling, and it is
    what makes a command that leaves and comes back keep its sequence.
    """
    candidates = [pin for pin in (pins.get(key), node.pin) if pin is not None and not strands_a_sibling(pin, node.name, sibling_names)]
    held = ledger.assignments.get(key)
    if held is not None:
        candidates.append(held)
    candidates.extend(reversed(ledger.retired.get(key, [])))
    return candidates


def assign_siblings(children: list[Node], parent_key: str, pins: dict[str, str], ledger: Ledger) -> dict[str, str]:
    """Assign one sibling set, writing each node's prefix and returning the new entries."""
    assigned: dict[str, str] = {}
    present = {key_of(node.path) for node in children}
    retired_claims = [
        Claim(key=key, name=name_of(key), prefix=prefix, live=False)
        for key, prefixes in ledger.retired.items()
        if parent_key_of(key) == parent_key
        for prefix in prefixes
    ]
    # A sibling still in the tree keeps its whole territory, so a node checked
    # before it cannot take a prefix that captures its name. A path gone from the
    # tree keeps only its string, as a retired one does.
    held_claims = [
        Claim(key=key, name=name_of(key), prefix=prefix, live=key in present)
        for key, prefix in ledger.assignments.items()
        if parent_key_of(key) == parent_key
    ]
    live_claims: list[Claim] = []

    def claims_against(key: str) -> list[Claim]:
        # A node is never blocked by its own ledger entries. That is what lets
        # it reclaim a retired prefix of its own, and lets its pin move it.
        return [claim for claim in retired_claims + held_claims if claim.key != key] + live_claims

    def accept(node: Node, key: str, prefix: str) -> None:
        node.prefix = prefix
        assigned[key] = prefix
        live_claims.append(Claim(key=key, name=node.name, prefix=prefix, live=True))

    sibling_names = [node.name for node in children]
    unlocked = []
    for node in children:
        key = key_of(node.path)
        for candidate in locks_for(node, key, pins, ledger, sibling_names):
            if is_valid(candidate, node.name, claims_against(key)):
                accept(node, key, candidate)
                break
        else:
            unlocked.append(node)

    for node in sorted(unlocked, key=lambda node: node.name):
        key = key_of(node.path)
        chosen = choose_prefix(node.name, sibling_names, claims_against(key))
        if chosen is not None:
            accept(node, key, chosen)
    return assigned


def assign(model: Model, ledger: Ledger, pins: dict[str, str]) -> Ledger:
    """Fill in every node's prefix and return the ledger to save.

    Locks are taken before free nodes across the whole sibling set rather than
    node by node, so an incumbent never loses its prefix to a newcomer that
    happened to sort earlier.
    """
    assignments: dict[str, str] = {}

    def descend(node: Node) -> None:
        assignments.update(assign_siblings([child for child in node.children if not child.excluded], key_of(node.path), pins, ledger))
        for child in node.children:
            descend(child)

    descend(model.root)
    return Ledger(tool=model.tool, assignments=assignments, retired=retire(ledger, assignments))


def retire(ledger: Ledger, assignments: dict[str, str]) -> dict[str, list[str]]:
    """Every prefix a path has held and no longer holds, oldest first.

    Covers both halves of "never recycled": a command that disappeared, and a
    command still present whose prefix changed under a new pin.
    """
    retired = {key: list(prefixes) for key, prefixes in ledger.retired.items()}
    for key, prefix in ledger.assignments.items():
        if assignments.get(key) != prefix and prefix not in retired.setdefault(key, []):
            retired[key].append(prefix)
    for key, prefix in assignments.items():
        if prefix in retired.get(key, []):
            retired[key].remove(prefix)
    return {key: prefixes for key, prefixes in retired.items() if prefixes}
