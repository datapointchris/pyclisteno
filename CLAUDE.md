# pyclisteno

A library that gives a Click or Typer CLI shortcuts made of prefixes of its own command names, run
together into one token, so `tool exgsr` runs `tool example-pipeline glue source-copy run`. A CLI
enrolls with one `attach(app)` call after its tree is complete, and drops the library by deleting
that call.

`attach` runs one pass: `walk` turns the tree into a `Model`, `assign` fills each node's prefix
against the ledger and the pins, `save_ledger` and `export` write the three files, and then
`expand_argv` and `teach` run if they were asked for. The public surface is `__all__` in
`__init__.py`, and it stays small because adoption is one line in and one line out.

## The library may never break the CLI it is attached to

- **`attach` returns `None` instead of raising.** Every step runs inside `enroll`, under one
  `except Exception`. A new step goes inside `enroll` so the catch covers it. Set `CLISTENO_DEBUG`
  to get the traceback. A test whose `attach` returns `None` for no visible reason needs it.
- **With `teaching` and `expanding` off, the CLI's stdout, stderr and exit codes are
  byte-identical.** `test_attaching_does_not_change_a_single_byte_the_cli_produces` runs every
  command at every level, bare and with `--help`, with and without enrollment. `walk` reads the tree
  and never mutates a command, which is what makes the property testable.
- **`teaching` is the only option that changes output, and `expanding` the only one that changes
  what runs.** Both default to off, so adopting the library commits to neither.
- **The pin file cannot stop startup.** A syntax error, a table of the wrong shape, or a pin that is
  not a prefix of its command's name costs that pin, never the run.

## There is no runtime dependency, click included

`dependencies` in `pyproject.toml` is empty. The Python floor is 3.11 because `tomllib` reads the
pin file without a TOML package.

- **The walk matches on shape, never on click's classes.** Typer 0.27 vendors a complete copy of
  click at `typer._click`, sharing no base class with the installed click. An `isinstance` check
  against `click.Command` sees a typer tree as no tree, and returns an empty model without an error.
  `CommandLike` in `walk.py` is the shape both implementations expose.
- **typer and rich are imported inside `try`/`except ImportError`**, in `walk.py`, `teach.py` and
  `markup.py`. An unguarded import makes either one a dependency of every consumer.
- **`fixture.py` imports typer at module level.** Nothing `__init__.py` imports may import it.

## Typer rebuilds its tree, so teaching writes to typer's records

Teaching sets `short_help` on each command, the string a parent's help row reads. No formatter,
template or rich style is touched. A click app's commands are the objects that run, so the write
lands on them. A typer app's `get_command` builds a fresh tree on every call, so a write to a
converted command is discarded when typer converts again to run. `teach` therefore writes to typer's
`CommandInfo` and `TyperInfo`. `enroll` passes it the original app, never the converted command.

Names come from typer's own `get_command_name`. `test_every_assigned_node_has_somewhere_to_write`
fails when they stop matching the walked tree. Without it, the failure is hints that silently stop
appearing.

`@shortcut` and `@no_shortcut` set an attribute on the callback, never an entry in a registry keyed
by name, because a tree built at runtime makes several commands from one callback. Typer wraps the
callback, and `functools.update_wrapper` copies the mark across. So the mark decorator goes under
`@app.command()`, as the README shows.

## A sequence, once handed out, never changes meaning

Everything in `assign.py` and `resolve.py` protects this. A recycled sequence still runs, and runs
something else.

- **The ledger is state, not cache.** It lives at `$XDG_STATE_HOME/clisteno/<tool>.json`. Deleting
  it changes what typed sequences mean. A key is the node path joined with spaces. A value is that
  node's prefix at its own level, never the run-together sequence, which would break every
  descendant when an ancestor's prefix changed.
- **Precedence is config pin, then `@shortcut`, then the ledger, then the computed minimum.** A lock
  that is not valid where it lands falls through to the next source. Locks are taken across a whole
  sibling set before any free node, so an incumbent never loses its prefix to a newcomer that sorts
  earlier.
- **One rule makes longest-match correct.** For any two live siblings A and B, if prefix(A) is a
  prefix of name(B), prefix(A) is at most as long as prefix(B). `is_valid` is that rule plus the
  reserved strings. `test_no_assignment_ever_lets_one_sibling_capture_another` sweeps it: every
  prefix of every name must reach that name.
- **`choose_prefix` prefers a prefix no sibling name shares.** `run` and `review` get `ru` and `re`,
  not a bare `r` for whichever sorts first. The fallback is for `run` beside `runs`, where no
  unambiguous prefix exists.
- **A prefix a path stops holding is retired**, whether the command was removed or re-pinned. No
  other node is issued it, and no new prefix may be short enough to swallow it. The path that held
  it may take it back.
- **Retirement cannot reach backwards, so resolution carries the other half.** A prefix issued
  before the retirement can still capture the retired string. `resolve` lets the retired string win
  its own longest match and resolve to nothing. Lengthening the incumbent instead would break a
  sequence in use to protect one nobody can use.
- **A ledger that fails to load stops enrollment before anything is written.** Pins degrade to empty
  on a bad file, and the ledger must not. An empty ledger saved over a damaged one reassigns every
  prefix.
- **Nothing reads `SCHEMA` back, and `Ledger.from_dict` indexes every field.** A field added as
  required makes every existing ledger fail to load. `attach` swallows that, so the tool silently
  loses its shortcuts until the ledger is deleted, and deleting it loses the grandfathering.

## Prefixes run together, so one string can name two paths

The typed sequence is every ancestor's prefix and the node's own with no separator: `exgsr`, not
`ex g s r`. Without level boundaries a string can parse two ways, and a string that does is two
paths concatenated. `unambiguous_sequences` publishes such a string for neither path. It also
withholds a sequence equal to a top-level command name, since typing that name must reach that
command.

`resolve` tries the whole first token as a sequence before the per-token walk. `exgsr` also starts
with `ex`, so the walk alone would answer `example-pipeline` and drop the rest. The index is keyed
by the whole sequence, because a prefix is unique only among its siblings.

## Expansion declines wherever it is not certain

`expanding` rewrites `sys.argv` before the CLI parses it. It is the one surface that can make a CLI
run something other than what was typed. An unknown token, a retired sequence and a leading option
all pass through untouched, for the CLI to answer itself. Expanding to the node reached before a
retired string would run an ancestor of a removed command.

argv is rewritten only when the basename of `argv[0]` is the tool. Enrollment runs at import, so
pytest collecting a module that calls `attach` would otherwise have its own arguments rewritten.

## The walk is ordered, so who built the tree cannot change the shortcuts

Click sorts its commands and typer keeps declaration order. Assignment reads siblings in order to
settle a contested prefix, so `build_node` sorts them. A hidden command is skipped, so it cannot
push a visible sibling onto a longer prefix. A summary is the first help paragraph, collapsed and
never truncated. Click and typer truncate their own, and nothing downstream recovers what was cut.

## The written files are a format, not an internal detail

- **`export` writes the model and the index from one walk.** Two walks either side of a tool
  upgrade would publish a prefix for a command the model does not hold.
- **The index is TSV so a shell can read it on every keystroke**, where parsing JSON costs a
  subprocess. The library writes the index and ships no shell code that reads it.
- **The index carries no markup and no metavars**, because both columns go onto a command line. A
  bracket is a rich tag only when rich's `Style.parse` accepts it, so `[RUN_ID]` and `[OPTIONS]`
  survive. The JSON model keeps the markup.
- **`write_atomically` skips a write whose content is unchanged.** That is the whole staleness
  check. The ledger is meant to be synced between machines, and a rewrite that changes only the
  mtime would wake the sync on every invocation. `test_a_second_attach_leaves_every_file_untouched`
  holds it.
- **State and cache are namespaced by library, the pin file by tool.** The pin file sits beside the
  tool's own config, where a user looks. `$XDG_STATE_HOME/<tool>/` can hold another library's
  per-machine state that must never sync, so the synced ledger lives under `clisteno/` instead.
  `test_paths.py` pins that asymmetry.
- **The names and fields are written for implementations in other languages to share.** They are
  the node fields and index columns, which `SCHEMA` versions, plus the ledger keying, the
  `clisteno` directory and the pin filename. The pin filename carries no language prefix for that
  reason. Renaming any of them is a format change, not a refactor.

## The hostile fixture is a spec, so new cases go in `tests/apps.py`

`src/pyclisteno/fixture.py` ships in the package as the tree an implementation in any language
tests against. Its docstring lists each case and the assumption it breaks.
`test_the_hostile_fixture_assigns_as_designed` pins every prefix it receives. A test needing another
tree builds one in `tests/apps.py`. `app_with` gives its app a callback because typer collapses a
single-command app into a bare command with no children.

## A test that writes sets its own XDG directories

No conftest isolates them. A test that reaches `attach`, `save_ledger` or `export` sets
`XDG_CONFIG_HOME`, `XDG_STATE_HOME` and `XDG_CACHE_HOME` itself, as the `stores` fixture in
`test_attach.py` does. Without that it writes into the developer's real ledger and cache.

## The hook and CI configs are generated, and a hand edit is reverted

`.pre-commit-config.yaml`, `.github/workflows/validate.yml`, `.github/actionlint.yaml`,
`.editorconfig`, `.markdownlint.yaml`, `.shellcheckrc` and the `pyproject.toml` tool keys listed as
managed come from a shared template. The next regeneration overwrites a hand edit to any of them.
`release.yml` belongs to the repo.

## A push to main releases to PyPI, and a published version is permanent

A push to `main` runs `validate.yml`, then python-semantic-release cuts the version and tag from the
commits. The `publish` job then builds from the tag and uploads to PyPI through Trusted Publishing.
It sits in `release.yml` because a tag pushed with `GITHUB_TOKEN` starts no other workflow, and the
PyPI publisher names this workflow file and its `pypi` environment. A version on PyPI cannot be
replaced, only yanked.

On 0.x a breaking change cuts a minor, through `major_on_zero = false`. Removing that key is how the
project reaches 1.0. Release notes go in the GitHub release body, and there is no changelog file.
