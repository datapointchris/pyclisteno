"""Learned shortcut, hint, and completion layer for Click and Typer CLIs.

The public surface is deliberately tiny, because the library's value proposition
is that a CLI can adopt it in one line and drop it in one line. `attach` walks a
finished command tree; the decorators only record exceptions to what `attach`
would otherwise compute.
"""

from pyclisteno.attach import attach
from pyclisteno.marks import no_shortcut
from pyclisteno.marks import shortcut
from pyclisteno.model import SCHEMA
from pyclisteno.model import Model
from pyclisteno.model import Node
from pyclisteno.resolve import expand
from pyclisteno.resolve import expand_argv
from pyclisteno.resolve import resolve
from pyclisteno.walk import walk

__all__ = ['SCHEMA', 'Model', 'Node', 'attach', 'expand', 'expand_argv', 'no_shortcut', 'resolve', 'shortcut', 'walk']
