"""The two decorators, and the one place that reads what they leave behind.

A mark lives on the callback function rather than in a registry keyed by command
name, because a tree assembled at runtime produces several commands from one
callback and a name-keyed registry cannot tell them apart.

Typer does not hand its Click command the function you decorated — it builds a
wrapper and calls the original inside it. `functools.update_wrapper` copies the
wrapped function's `__dict__`, so a mark set before `@app.command()` survives
that rebuild. The decorator must therefore be applied *under* the command
decorator, which is the order the README documents.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

SHORTCUT_ATTRIBUTE = '__clisteno_shortcut__'
EXCLUDED_ATTRIBUTE = '__clisteno_excluded__'

Function = TypeVar('Function', bound=Callable)


def shortcut(prefix: str) -> Callable[[Function], Function]:
    """Pin a prefix rather than accept the computed one."""

    def mark(function: Function) -> Function:
        setattr(function, SHORTCUT_ATTRIBUTE, prefix)
        return function

    return mark


def no_shortcut(function: Function) -> Function:
    """Keep a command off the fast path entirely."""
    setattr(function, EXCLUDED_ATTRIBUTE, True)
    return function


def pinned_prefix(callback: Callable | None) -> str | None:
    if callback is None:
        return None
    return getattr(callback, SHORTCUT_ATTRIBUTE, None)


def is_excluded(callback: Callable | None) -> bool:
    """A group defined without a callback has nothing to carry a mark, and is never excluded."""
    if callback is None:
        return False
    return getattr(callback, EXCLUDED_ATTRIBUTE, False)
