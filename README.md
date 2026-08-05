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

Removing the library is deleting those two lines. Commands are never modified, and the CLI's
behaviour with `attach()` is byte-identical without it — stdout, stderr, and exit codes — which is
asserted by the test suite rather than assumed.

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
parses shortcuts and never needs to know this library exists.

## Related

`goclisteno` and `bashclisteno` implement the same grammar schema and the same assignment
algorithm for their ecosystems, in the way `goselfupdate` / `pyselfupdate` / `bashselfupdate`
share one release contract.
