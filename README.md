# pyclisteno

A learned shortcut, hint, and completion layer for Python CLIs built on Click or Typer.

Stenography compresses language by rule rather than by lookup table, which is why trained
stenographers reach speed without memorising a second vocabulary. `clisteno` does the same thing
to a command tree: the short form of a command is a literal prefix of the long form, so typing
`dectl sa gl so ru` is typing `dectl salesdata glue source-copy run` with less of it, not typing
an alias that has to be learned separately.

## What it provides

Three surfaces over one model, each independently opt-in:

- **Teaching** — the short form and its description shown beside the long form in help output, so
  ordinary use trains the fast path.
- **Prediction** — grammar-aware ghost text in the shell, driven by a cached index rather than by
  history.
- **Compression** — a resolver that expands a prefix sequence into the full command.

## Attaching it

Enrollment is one call after the command tree is complete. It is not a decorator on each command,
because a tree assembled at runtime from config has no functions to decorate:

```python
from pyclisteno import attach

app = typer.Typer()
# ... build the tree, including anything driven by config ...
attach(app)
```

Removing the library is deleting those two lines. Nothing about the CLI changes: with `attach()`
as written above, stdout, stderr and exit codes are byte-identical without it, at every level of
the tree and for every `--help`, which the test suite asserts rather than assumes.

Teaching is the one surface that changes what a CLI prints, so it is asked for explicitly:

```python
attach(app, teaching=True)
```

Each row in a parent's help then carries the short form of the command it names.

```text
run      (ru) Run the thing, and keep running it until something says otherwise.
runs     (runs) List previous runs.
destroy  Delete everything, permanently and without confirmation.
```

`runs` shows its whole name because `run` is a strict prefix of it, and `destroy` shows no short
form at all — see `@no_shortcut` below.

Compression is the other half, and the half that makes the offer true: without it the short form
is advice the tool would reject.

```python
attach(app, teaching=True, expanding=True)
```

`expanding` rewrites a typed sequence into the command it stands for before the CLI parses it, so
`tool ex g s r` runs `tool example-pipeline glue source-copy run`. It is the only surface that can
make a CLI run something other than what was typed, so it declines wherever it is not certain: an
unknown token, a retired sequence, or anything after a leading option is passed through untouched
for the CLI itself to answer. A real command name expands to itself, because a name starts with
its own prefix and no sibling's can outmatch it.

Decorators exist only for exceptions:

```python
@app.command()
@shortcut('ru')  # pin, rather than accept the computed prefix
def run(): ...


@app.command()
@no_shortcut  # keep a destructive verb off the fast path
def destroy(): ...
```

## How prefixes are assigned

Each node gets the shortest prefix of its own name that is unambiguous among its siblings, so
`run` and `review` become `ru` and `re`. Assignments are recorded and **grandfathered**: once a
prefix has been handed out it is never shortened, lengthened, or reassigned, because the whole
point is protecting a sequence already in someone's fingers. Resolution is longest-match, which is
what lets an incumbent `r` coexist with a later `re`. A removed command's prefix is retired
permanently rather than recycled — a recycled sequence still works and silently does something
else, which is the worst failure available here.

## Where it keeps things

| Path | What | Class |
| --- | --- | --- |
| `$XDG_CONFIG_HOME/<tool>/clisteno-shortcuts.toml` | User pins | Config — you write it, nothing else does |
| `$XDG_STATE_HOME/clisteno/<tool>.json` | The assignment ledger | State — synced, so a sequence means the same thing on every machine |
| `$XDG_CACHE_HOME/clisteno/<tool>.json` | The grammar model | Cache |
| `$XDG_CACHE_HOME/clisteno/<tool>.tsv` | Flat index for the shell | Cache |

The config file sits beside the tool's own config and is never merged into it, so the tool never
parses shortcuts and never needs to know this library exists. Its keys are node paths and its
values are that node's prefix at its own level, which is also how the ledger is keyed:

```toml
[shortcuts]
run = "ru"
"glue nightly" = "ni"
```

A pin that is unusable — not a prefix of the command's own name, or already spoken for — is
dropped and the prefix computed as if it were absent. Nothing in that file can stop the CLI
starting, including a syntax error in it.

## Related

`goclisteno` and `bashclisteno` implement the same grammar schema and the same assignment
algorithm for their ecosystems, in the way `goselfupdate` / `pyselfupdate` / `bashselfupdate`
share one release contract.
