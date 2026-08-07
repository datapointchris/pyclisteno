"""A deliberately hostile CLI, shipped so every language port tests one grammar.

dectl's own grammar is too clean to exercise the hard paths — one closed verb
vocabulary and a single structural rule — and testing against it would turn every
dectl command change into a test change. Everything here is a case that broke, or
would break, an assumption:

- `run` / `runs` / `review`, a three-way first-letter collision where one name is
  a strict prefix of another. `run` can never be a unique prefix of itself.
- `glue`, a namespace that also takes an argument.
- The per-job subtree, built at runtime from a dict the way dectl's job aliases
  arrive from config — the case decorators cannot reach.
- `source-copy`, hyphenated.
- `destroy`, marked `@no_shortcut`.
- `debug-dump`, hidden, which must not consume a prefix its visible siblings want.

It lives in the library rather than in `tests/` because the exported grammar is
part of the shared spec: goclisteno and bashclisteno test against these cases
instead of each inventing their own. Importing it needs typer, which the library
itself never does.
"""

from __future__ import annotations

import typer

from pyclisteno.marks import no_shortcut
from pyclisteno.marks import shortcut

JOBS = {
    'nightly': 'The overnight full load.',
    'hourly': 'The hourly delta.',
}


def build_job_app(job_help: str) -> typer.Typer:
    job = typer.Typer(help=job_help)

    @job.command()
    def run() -> None:
        """Start the job and wait for it."""

    @job.command()
    def review() -> None:
        """Read the last outcome."""

    return job


def build_glue_app() -> typer.Typer:
    glue = typer.Typer(help='Work on one glue source, named by alias.')

    @glue.callback()
    def resolve_alias(alias: str) -> None:
        """Resolve an alias to a source before running anything under it."""

    @glue.command(name='source-copy')
    def source_copy() -> None:
        """Copy the source definition to another environment."""

    for job_name, job_help in JOBS.items():
        glue.add_typer(build_job_app(job_help), name=job_name)

    return glue


def build_fixture_app() -> typer.Typer:
    """A fresh app per call, because a module-level one accumulates state across tests."""
    app = typer.Typer(help='A CLI built to break prefix assignment.')

    @app.command()
    @shortcut('ru')
    def run() -> None:
        """Run the thing, and keep running it until something says otherwise."""

    @app.command()
    def runs() -> None:
        """List previous runs."""

    @app.command()
    def review() -> None:
        """Review the most recent run."""

    @app.command()
    @no_shortcut
    def destroy() -> None:
        """Delete everything, permanently and without confirmation."""

    @app.command(hidden=True)
    def debug_dump() -> None:
        """Dump internal state."""

    app.add_typer(build_glue_app(), name='glue')
    return app
