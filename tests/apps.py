"""Small apps built to order, for cases the shipped hostile fixture does not cover.

The fixture is fixed on purpose — it is the shared spec the language ports test
against — so anything that needs a tree of its own builds one here.
"""

import typer

from pyclisteno.marks import no_shortcut
from pyclisteno.marks import shortcut


def make_callback(name, pin=None, excluded=False):
    def command():
        pass

    command.__doc__ = f'The {name} command.'
    if pin is not None:
        command = shortcut(pin)(command)
    if excluded:
        command = no_shortcut(command)
    return command


def app_with_markup():
    """Help text carrying rich tags, which is legitimate for a Python CLI.

    cli-design.md settles that Python help is rich's, so a tool's own summaries
    reach the dump with tags in them — dectl's alias rows are the live example.
    """
    app = typer.Typer(help='A [bold]marked up[/bold] app.')
    app.callback()(lambda: None)

    @app.command(name='source-copy', help='Copy [bold]source-copy[/bold] to another environment.')
    def source_copy() -> None:
        pass

    @app.command(name='logs', help='Show logs [RUN_ID] for the run.')
    def logs() -> None:
        pass

    return app


def app_with(*names):
    """A flat app whose commands are exactly the names given.

    The callback is not decoration: typer collapses an app holding a single
    command into a bare command with no children, and half these cases are about
    what one command does on its own.
    """
    app = typer.Typer()
    app.callback()(lambda: None)
    for name in names:
        app.command(name=name)(make_callback(name))
    return app
