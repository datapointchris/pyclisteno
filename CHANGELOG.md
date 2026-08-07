# CHANGELOG


## v0.7.0 (2026-08-07)

### Features

- Expand a typed sequence before the CLI parses it
  ([`bb1dcbe`](https://github.com/datapointchris/pyclisteno/commit/bb1dcbe7f78481cfb95feed01c555a5c169b21d9))

attach(app, expanding=True) rewrites argv, so `tool ex g s r` runs `tool example-pipeline glue
  source-copy run`. Without it the teaching hint offers a command the tool rejects, which makes this
  the half that turns the short form from advice into something that works.

The only surface here that can make a CLI run something other than what was typed, so it declines
  wherever it is not certain rather than guessing: an unknown token, a retired sequence, and
  anything following a leading option all pass through for the CLI to answer itself. Expanding to
  the node reached *before* a retired sequence would run an ancestor of a command that no longer
  exists, which is the silent wrong answer retirement exists to prevent.

A real command name expands to itself. A name starts with its own prefix and no sibling's prefix can
  outmatch it — the invariant assignment maintains is exactly what keeps this from shadowing
  anything.


## v0.6.2 (2026-08-07)

### Bug Fixes

- Key the index by the typed sequence, not the node's prefix
  ([`87fc0c4`](https://github.com/datapointchris/pyclisteno/commit/87fc0c4fd4deee1b2a67b89c2e345d70f685f103))

A prefix is unique only among siblings, so the flat index handed the shell eleven colliding keys on
  dectl alone — `r` alone named five different commands, and `l` three. Nothing could look anything
  up in it, which is the one job the file has.

Column one is now every ancestor's prefix followed by the node's own: what a user actually types,
  and unique by construction. A node under an unassigned parent is dropped rather than given a
  sequence nothing can reach.


## v0.6.1 (2026-08-07)

### Bug Fixes

- Strip rich tags from the index the shell reads
  ([`3820d21`](https://github.com/datapointchris/pyclisteno/commit/3820d21be91703dba12434a1d44813bb42b2cbdb))

dectl's first real dump exposed it: its summaries carry markup, because Python help is rich's, so
  the flat index handed the shell rows reading "Glue job [bold]source-copy[/bold] →
  my-{env}-source-copy-job". That column goes onto the command line, where those are literal
  characters.

The JSON keeps the tags — a rich-aware renderer wants them — and only the index loses them, so the
  model stays a faithful record and the rich knowledge sits in one function.

The rule is rich's own: a bracket is a tag when Style.parse accepts what is inside it. That keeps
  [id], [OPTIONS] and [RUN_ID], which is what a help row means by square brackets and exactly what a
  blunt strip would have eaten.


## v0.6.0 (2026-08-07)

### Documentation

- Document teaching and the pin file format
  ([`fd140df`](https://github.com/datapointchris/pyclisteno/commit/fd140df217259da7a3d4b38facdbf7534acec96e))

"Commands are never modified" was true until teaching shipped, and the pin file had a format nothing
  described. Both now say what the code does, including that an unusable pin is dropped rather than
  raised on.

### Features

- Show each command's short form in its parent's help
  ([`4117393`](https://github.com/datapointchris/pyclisteno/commit/4117393b4ddffc29499172ce0503986a7a9f1850))

attach(app, teaching=True) writes the assigned prefix into the row a parent renders for each child,
  so ordinary use trains the fast path. Off by default, because it is the one surface that
  deliberately changes what a CLI prints.

run (ru) Run the thing, and keep running it until something… runs (runs) List previous runs. destroy
  Delete everything, permanently and without confirmation.

It writes short_help rather than patching the renderer, which is what keeps it compatible with the
  settled rule that Python help is rich's with rich's defaults — a library that swapped the
  formatter would make every tool adopting it the odd one.

Where it writes depends on who built the tree, and getting it wrong fails silently. A click command
  is the object that runs, so writing to it works. A typer one is not: get_command rebuilds the tree
  on every call, so the first attempt mutated commands that were then thrown away and the hint never
  appeared. The durable target is typer's own CommandInfo and TyperInfo. Names come from typer's
  get_command_name rather than a reimplementation of its rules, with a test that fails if that ever
  stops lining up with the walked tree.

Parentheses, not brackets — the help rows already use <id> and [id] for required and optional
  arguments.


## v0.5.0 (2026-08-07)

### Features

- Enroll a CLI in one call with attach()
  ([`89e9f53`](https://github.com/datapointchris/pyclisteno/commit/89e9f5372816f0f6b829949851cb72b224d5701f))

Walks, assigns, and publishes the two cache files and the ledger. The tool name is inferred from the
  command, falling back to the invoked script, so adoption stays the single argument the README
  promises.

Nothing escapes to the caller. A read-only cache directory or a truncated ledger costs enrollment
  and nothing else, because a tool that dies for either is a tool this library broke; CLISTENO_DEBUG
  re-raises, since a failure nobody can see is its own kind of broken.

No staleness check, and no fingerprint field on the model to support one. Assignment is pure
  computation over a tree already in memory, so recomputing costs less than deciding whether to, and
  write_atomically now skips a write whose content already matches. The rendered text is the
  fingerprint: nothing to store, and no way for a stored one to disagree with the file it describes.
  It earns its place on the ledger, which is synced — an identical rewrite still moves the mtime and
  would wake Syncthing on every invocation of every tool.

Covers the non-invasiveness test: every fixture command at every level, bare and with --help,
  byte-identical with and without enrollment.


## v0.4.0 (2026-08-07)

### Features

- Assign grandfathered prefixes and resolve them back
  ([`e6095a3`](https://github.com/datapointchris/pyclisteno/commit/e6095a3ee1ae3393b931f92b92da496debe1bebf))

Each node takes the shortest prefix of its own name that no sibling name shares, so review and run
  become re and ru rather than one of them taking a bare r that means nothing definite. The ledger
  grandfathers whatever was handed out before, so a sibling arriving later lengthens its own prefix
  and never an incumbent's. Precedence runs config pin, source pin, ledger, computed, each falling
  through to the next where it does not fit.

Correctness reduces to one rule over live siblings A and B: if prefix(A) is a prefix of name(B) then
  prefix(A) is no longer than prefix(B). That is what stops runs taking ru or run while run holds r,
  and it is checked directly by a sweep asserting every prefix of every name reaches its own
  command.

Retirement needed splitting in two. A retired string is never reissued and no new prefix may be
  short enough to swallow it, but neither rule reaches backwards: a prefix assigned before the
  retirement can still capture it. Taking it off the incumbent would break a sequence in use today
  to protect one nobody can use at all, so resolution lets a retired string win its own longest
  match and stop there.


## v0.3.0 (2026-08-07)

### Chores

- Sync shellcheckrc from the toolchain die
  ([`4681511`](https://github.com/datapointchris/pyclisteno/commit/468151149d242b1ec58b6e09f7356f756c46f9a4))

SC1091/SC1090 go off fleet-wide, with source-following kept on so a variable set in one file and
  consumed in a library it sources still resolves. Matches pre-commit/configs/shellcheckrc.ini
  verbatim.

### Features

- Walk the command tree into the grammar model
  ([`8a15fdd`](https://github.com/datapointchris/pyclisteno/commit/8a15fdd5af93162ff32b3b42231f0e1981b6324f))

Exports the live Click or Typer tree as the JSON model and the flat TSV index the shell reads, with
  every node carrying its path, kind, typeable invocation, untruncated summary and argument flag.
  Prefixes stay unset — assignment is the next pass.

The walk matches on shape rather than on click's classes. Typer 0.27 vendors a complete copy of
  click whose Command derives from ABC and shares no base class with the installed one, so an
  isinstance check sees a Typer tree as no tree at all and returns an empty model. Matching the
  shape both expose costs the library its last runtime dependency.

Siblings are sorted because click sorts its commands and Typer keeps declaration order, and
  assignment reads siblings in order to decide who keeps a contested prefix.


## v0.2.1 (2026-08-06)

### Bug Fixes

- Ship py.typed so consumers see the annotations
  ([`35572f7`](https://github.com/datapointchris/pyclisteno/commit/35572f788174230e44d41aa0dcacab78c50d3918))

The pyproject has carried the Typing :: Typed classifier since the repo was created, but PEP 561
  requires the marker file for a consumer's type checker to read an installed package's annotations
  at all. Without it the classifier is a claim nothing honours: every annotation in the package was
  invisible downstream, and a caller passing the wrong type got no error.

Found while extracting pytermstyle, which used this repo as its template. pyselfupdate already ships
  the marker.

### Build System

- Declare pytest-cov and ignore coverage artifacts
  ([`b45288d`](https://github.com/datapointchris/pyclisteno/commit/b45288dde2069d83438ea8ef986ab989a8e9c0bd))

The Taskfile has had a test:coverage target passing --cov since it was written, while pytest-cov
  appeared in neither pyproject.toml nor uv.lock, so the target could not run. Declaring it makes
  the task work rather than removing a target that should exist.

.gitignore gains the entries from forge's new sync-gitignore die: .coverage, coverage.xml, dist/ and
  *.egg-info/. It previously tracked nothing but .planning while the Taskfile's clean target removed
  four artifacts, so a coverage run here would have offered .coverage up for commit. .venv, htmlcov,
  .pytest_cache and .ruff_cache are absent on purpose — each tool writes a self-ignoring .gitignore
  into the directory it creates.


## v0.2.0 (2026-08-05)

### Continuous Integration

- Drop the PyPI publish job until the channel is decided
  ([`45e1c8f`](https://github.com/datapointchris/pyclisteno/commit/45e1c8f8b23e7b15b5d7b02ee42753725b626c89))

The publish job fired on the first push and failed: Trusted Publishing is not configured on PyPI, so
  uv publish got a valid OIDC token with no matching publisher. The version job succeeded, so v0.1.0
  is tagged and released on GitHub.

Removing the job rather than leaving it red. Consumers can take a git dependency against the tag in
  the meantime, and the comment in its place records the two non-obvious things about its shape so
  restoring it is a copy from pyselfupdate plus configuring the publisher.

### Features

- Resolve the four XDG paths the library reads and writes
  ([`133d715`](https://github.com/datapointchris/pyclisteno/commit/133d7156ddf42a43abd2ac0cf4317606400aee03))

Pins, the assignment ledger, the walked model, and the shell index. The nesting is deliberately not
  uniform: pins are namespaced by tool so they sit beside that tool's own config, while state and
  cache are namespaced by library.

The inversion is load-bearing. ~/.local/state/<tool>/ already holds pyselfupdate's autoupdate.json,
  which records the version installed on this machine and must never replicate; the ledger must
  replicate, or the same typed sequence resolves differently per box. One shared directory keeps
  both true and means adopting the library costs no new synced folder.

Tests pin the parts most likely to be tidied back into symmetry later, and assert the pins filename
  carries no language prefix, since goclisteno and bashclisteno have to produce the identical name
  for the shell to read any of them.

Restores the PyPI publish job now that a pending publisher is registered, with the environment-claim
  requirement written into the comment.


## v0.1.0 (2026-08-05)

### Chores

- Add .planning to gitignore
  ([`eff68e0`](https://github.com/datapointchris/pyclisteno/commit/eff68e00e7a6155dcbe046fe61cd21995187e8bf))

### Continuous Integration

- Add the semantic-release and PyPI publish workflow
  ([`c08c1d1`](https://github.com/datapointchris/pyclisteno/commit/c08c1d1eee251dd0e3c4de38b0bd04b87c2f2f1d))

Copied from pyselfupdate, which is the settled shape for a Python library on this fleet:
  semantic-release decides the version and tags in one job, publish runs as a gated second job in
  the same workflow because a tag pushed with GITHUB_TOKEN never triggers another run, and only the
  publish job carries id-token: write for Trusted Publishing.

PyPI rather than the exploratory private index: this is a dependency other tools import, not a
  uv-installed CLI, so none of the git-pin apparatus applies. The private index exists because the
  good CLI names are already taken on PyPI, which is not a problem a new name has.

### Features

- Bootstrap pyclisteno
  ([`58d12a2`](https://github.com/datapointchris/pyclisteno/commit/58d12a23cfcb83fdf75ad466ec4fa49195362ccd))

A learned shortcut, hint, and completion layer for Click and Typer CLIs. The short form of a command
  is a literal prefix of the long form, so the fast path is the slow path with less typing rather
  than a second vocabulary to memorise.

Registered in ~/dev/repos.json first, then generated by the forge dies: pre-commit hooks and tool
  configs, the pyproject managed-key merge, the CI workflow, and the .planning symlink. Given a
  Taskfile at bootstrap rather than joining the Python tools that lack one.
