"""Learned shortcut, hint, and completion layer for Click and Typer CLIs.

The public surface is deliberately tiny, because the library's value proposition
is that a CLI can adopt it in one line and drop it in one line. `attach` walks a
finished command tree; the decorators only record exceptions to what `attach`
would otherwise compute.
"""
