"""Removing rich's tags from a summary, without removing brackets that mean something.

The JSON model keeps the markup. The summary there is the tool's own help text,
and a consumer that renders through rich wants it intact — cli-design.md settles
that Python help *is* rich's, so a Python tool's help strings legitimately carry
tags where a Go tool's never would.

The TSV cannot keep it. That column goes onto the command line, where `[bold]`
is four literal characters in a hint.

**The rule is rich's own rather than a guess.** `[bold]`, `[/bold]` and
`[bold red]` are tags because `Style.parse` accepts them; `[id]`, `[OPTIONS]` and
`[RUN_ID]` are not, and those are exactly what a help row means by square
brackets — the convention for an optional argument. A blunt bracket strip would
eat the grammar this library exists to teach.

rich is not a dependency. It arrives with typer, and a tool whose help has no
markup has nothing here to strip, so its absence is not a problem to solve.
"""

from __future__ import annotations

import re
from collections.abc import Callable

try:
    from rich.style import Style

    parse_style: Callable[[str], object] | None = Style.parse
except ImportError:
    parse_style = None

TAG = re.compile(r'\[([^\[\]]*)\]')


def is_tag(body: str) -> bool:
    """`[/]` closes whatever is open, and parses as the null style."""
    if parse_style is None:
        return False
    try:
        parse_style(body.removeprefix('/'))
    except Exception:
        # Any style rich cannot parse is not a tag rich would have rendered, so
        # it is text the tool meant to print. Broad because rich raises several
        # unrelated error types for a bad colour, a bad word, and bad syntax.
        return False
    return True


def strip_markup(text: str) -> str:
    stripped = TAG.sub(lambda match: '' if is_tag(match.group(1)) else match.group(0), text)
    return ' '.join(stripped.split())
