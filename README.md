# pyclisteno

A library that gives a Click or Typer CLI shortcuts made of prefixes of its own command names, run
together into one token. Under a tool called `tool` with a `jobs run` command, typing `tool jru`
runs `tool jobs run`. A CLI enrolls with one `attach(app)` call after its tree is complete. It
drops the library by deleting that call.

Stenography compresses language by rule rather than by lookup table. That is why trained
stenographers reach speed without memorizing a second vocabulary. This library does the same to a
command tree. Each level contributes a prefix of its own name. The prefixes run together into one
stroke. Its nearest neighbor is a shell alias. An alias is a second name to learn. A sequence is
the command's own name with less of it typed.

The library writes an index for a shell widget, such as a completion or a suggestion, to read on
every keystroke. It ships no shell code that reads it.

## Install

```bash
pip install pyclisteno    # or, in a uv project: uv add pyclisteno
```

It needs Python 3.11 or later. 3.11 is the floor because `tomllib` reads the pin file without a
TOML package. There are no runtime dependencies, click included. The walk matches on the attributes
click and typer both expose. It needs neither installed, because the CLI being enrolled brings its
own.

## Starting from scratch

Save this as `tool`, with no extension:

```python
import typer

from pyclisteno import attach

app = typer.Typer()
jobs = typer.Typer(help='Work on the pipeline jobs.')
app.add_typer(jobs, name='jobs')


@app.command()
def status():
    """Show what is running."""


@jobs.command()
def run(name: str):
    """Start a job and wait for it."""
    print(f'running {name}')


@jobs.command()
def review():
    """Read the last outcome."""


attach(app, teaching=True, expanding=True)

if __name__ == '__main__':
    app()
```

Then, in the same directory:

```bash
python3 -m venv .venv && . .venv/bin/activate   # any Python from 3.11
pip install pyclisteno typer        # typer for the demo; pyclisteno needs neither
python tool --help                  # each row carries its sequence: (s), (j)
python tool jobs --help             # a nested row carries the whole sequence: (jru), (jre)
python tool jru nightly             # runs `tool jobs run nightly`: prints "running nightly"
cat "${XDG_CACHE_HOME:-$HOME/.cache}/clisteno/tool.tsv"   # the index the run wrote
```

The file has no extension because the tool's name is what the user types. `attach` takes the name
from the app, or from the basename of `argv[0]` when the app has none. Expansion rewrites `argv`
only when that basename is the tool's name. A test runner that imports the module keeps its own
arguments for that reason. An installed console script called `tool` meets the rule. Run as
`tool.py`, the tool's name would be `tool.py`.

When no row carries a sequence, `attach` returned `None`. It never raises. Set `CLISTENO_DEBUG` to
any non-empty value to get the traceback instead.

The first run writes three files: the ledger under `$XDG_STATE_HOME`, and the model and the index
under `$XDG_CACHE_HOME`. The section on where it writes gives each path.

## Sequences — one prefix per level, run together into one token

Each command gets the shortest prefix of its own name that no sibling's name shares. `run` and
`review` become `ru` and `re`. A command's sequence is its ancestors' prefixes and its own, with no
separator. The prefixes are typed together: `tool j ru` expands `j` to `jobs` and hands `ru` to the
CLI, which rejects it.

Where no unambiguous prefix exists, as for `run` beside `runs`, `run` falls back to a shorter shared
prefix. `runs` takes its own full name. Resolution is longest match, so typing `run` still reaches
`run`. Longest match is also what lets an incumbent `r` coexist with a later `re`.

Two paths whose sequences run together into the same string are published by neither. Nothing could
tell which one was meant. A sequence equal to a top-level command's name is withheld too, so typing
that name reaches that command.

Siblings are sorted before assignment. Click sorts its commands. Typer keeps declaration order.
Without the sort, the same tree would get different shortcuts depending on which library built it.
A hidden command gets no prefix, so it cannot push a visible sibling onto a longer one.

**Assignments are recorded in a ledger and grandfathered.** Assignment never shortens, lengthens or
reassigns a prefix it has handed out, because the point is protecting a sequence already in
someone's fingers. Adding a `restart` command beside `run` and `review` in the demo leaves `review`
at `jre`. The same three commands assigned from an empty ledger give `review` the sequence `jrev`.

**A removed command's prefix is retired, never recycled.** No other command is issued it. No prefix
assigned afterwards may be short enough to swallow it. Typing it passes through to the CLI's own
error. A recycled sequence would still run, and run something else, which is the worst failure
available here. The command that held a retired prefix takes it back if it returns.

## `attach` — one call after the tree is built, and one deletion to drop it

```python
from pyclisteno import attach

app = typer.Typer()
# ... build the tree, including anything driven by config ...
attach(app)
```

Enrollment is one call rather than a decorator on each command. A tree assembled at runtime from
config has no functions to decorate.

With `teaching` and `expanding` off, the CLI's stdout, stderr and exit codes are byte-identical with
and without `attach`. The test suite asserts it rather than assuming it. It runs every command at
every level, bare and with `--help`, with and without enrollment, and compares the two.

`attach` never raises. Every step runs under one catch, so a read-only cache directory or a
truncated ledger costs the shortcuts and never the CLI. It returns the assigned `Model`, or `None`
when anything failed.

Its other arguments are `tool`, `version`, `teaching` and `expanding`. `tool` is the name users
type, inferred as [Starting from scratch](#starting-from-scratch) describes when omitted. `version`
is recorded in the model as `tool_version`. `teaching` and `expanding` both default to off, so
adopting the library commits to neither.

`expand` and `resolve` answer what a list of tokens reaches in the `Model` that `attach` returns.

## `teaching` — the whole sequence printed beside each command, and the only option that changes output

```python
attach(app, teaching=True)
```

Each row in a parent's help carries the whole sequence of the command it names, in parentheses. The
whole sequence is what a reader can act on. A command's own prefix is unique only among its
siblings. Parentheses mark the hint because square brackets already mark an optional argument in a
help row.

Teaching sets each command's `short_help`, the string its parent's help row reads. No formatter,
template or rich style is touched.

The hostile fixture shipped in the package shows both kinds of row that get no hint:

```text
run      (ru) Run the thing, and keep running it until something says otherwise.
runs     List previous runs.
review   (re) Review the most recent run.
destroy  Delete everything, permanently and without confirmation.
```

`destroy` is marked `@no_shortcut`. `runs` holds the prefix `runs`, which is also its sequence.
That sequence is already a top-level command's name, so it is withheld.

## `expanding` — a typed sequence rewritten before the CLI parses it, and declined wherever it is not certain

```python
attach(app, teaching=True, expanding=True)
```

Without expansion, a taught sequence is advice the CLI would reject. `expanding` rewrites
`sys.argv` before the CLI parses it, so `tool jru nightly` runs `tool jobs run nightly`. It is the
only option that can make a CLI run something other than what was typed. So it declines wherever it
is not certain. Each of these passes through untouched, for the CLI to answer itself:

- an unknown token
- a retired sequence
- a command line that starts with an option, such as `tool --env prod jru`

A real command name expands to itself. A token equal to a command's full name reaches that command
before any prefix is tried. That holds for a command with no prefix, such as a `run` added after
`runs` took `ru`. Exact match before prefix is the order argparse uses for abbreviated options.

Otherwise a token matches a command only between the command's prefix and its full name.
`"update --help"` passed as one argument starts with `update`'s prefix and still does not run
`update`.

## `@shortcut`, `@no_shortcut` and the pin file — exceptions to assignment, never the default

```python
from pyclisteno import no_shortcut, shortcut


@app.command()
@shortcut('ru')  # pin, rather than accept the computed prefix
def run(): ...


@app.command()
@no_shortcut  # keep a destructive verb off the fast path
def destroy(): ...
```

A mark goes under the command decorator, on the function itself. It is an attribute on the
callback, never an entry in a registry keyed by name. A tree built at runtime can make several
commands from one callback.

The pin file lets a user pin a prefix without touching the source. It sits beside the tool's own
config and is never merged into it. The tool never parses shortcuts and never needs to know this
library exists.

```toml
[shortcuts]
run = "ru"
"glue nightly" = "ni"
```

Its keys are node paths joined with spaces. Its values are that node's prefix at its own level,
never the run-together sequence. The ledger is keyed the same way.

**Precedence is the pin file, then `@shortcut`, then the ledger, then the computed prefix.** A pin
in either place outranks its own command's ledger entry. It is the one input that moves a
handed-out prefix, and it moves only its own command's. An unusable pin falls through to the next
source. A pin is unusable when any of these holds:

- it is not a prefix of its command's name
- another command at that level holds the prefix, or retired it
- it would make typing a sibling's name reach the pinned command

Nothing in the pin file can stop the CLI starting, a syntax error included.

## Where it writes — the ledger is state to sync, and the model and the index are cache

| Path | What | Class |
| --- | --- | --- |
| `$XDG_CONFIG_HOME/<tool>/clisteno-shortcuts.toml` | The pin file | Config: a person writes it, and the library only reads it |
| `$XDG_STATE_HOME/clisteno/<tool>.json` | The ledger | State: meant to be synced, so a sequence means the same thing on every machine |
| `$XDG_CACHE_HOME/clisteno/<tool>.json` | The model | Cache |
| `$XDG_CACHE_HOME/clisteno/<tool>.tsv` | The index | Cache |

An unset XDG variable falls back to its default: `~/.config`, `~/.local/state` or `~/.cache`.

Deleting the ledger changes what typed sequences mean. Every prefix is computed again, and every
grandfathered one is lost.

The pin file is namespaced by tool, because that is where a user looks for a tool's settings. State
and cache are namespaced by library. `$XDG_STATE_HOME/<tool>/` can hold another library's
per-machine state that must never be synced. The ledger lives under `clisteno/` so that syncing it
syncs nothing else.

A write whose content is unchanged is skipped. An identical rewrite would still move the mtime. A
file-sync tool would then wake on every run. Each write goes to a scratch file beside the target,
then is renamed into place. A shell reading the index never sees a torn file.

The index holds one line per published sequence: the sequence, the full command and its summary,
separated by tabs. A shell reads TSV with no subprocess, where parsing JSON would cost one per
keystroke. The index carries no rich markup and no argument metavars, because both columns go onto
a command line. The model keeps the markup.

## The files are a format, so an implementation in another language can share them

The model, the index, the ledger and the pin file carry nothing specific to Python. A library in
another language could implement the same assignment and read and write the same files. One shell
widget would then serve CLIs written in either. The model's `schema` field versions the node fields
and the index columns.

`pyclisteno.fixture` is a deliberately hostile command tree, shipped in the package, for such an
implementation to test against. Its docstring lists each case and the assumption it breaks.
Importing it needs typer.
