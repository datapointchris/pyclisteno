import pytest

from pyclisteno import paths

BASES = [
    ('XDG_CONFIG_HOME', paths.config_home, ('.config',)),
    ('XDG_STATE_HOME', paths.state_home, ('.local', 'state')),
    ('XDG_CACHE_HOME', paths.cache_home, ('.cache',)),
]


@pytest.mark.parametrize(('env_var', 'resolver', 'fallback'), BASES)
def test_base_prefers_the_environment_variable(env_var, resolver, fallback, monkeypatch, tmp_path):
    monkeypatch.setenv(env_var, str(tmp_path / 'elsewhere'))
    assert resolver() == tmp_path / 'elsewhere'


@pytest.mark.parametrize(('env_var', 'resolver', 'fallback'), BASES)
def test_base_falls_back_under_home_when_unset(env_var, resolver, fallback, monkeypatch, tmp_path):
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    assert resolver() == tmp_path.joinpath(*fallback)


@pytest.mark.parametrize(('env_var', 'resolver', 'fallback'), BASES)
def test_base_expands_a_tilde_in_the_environment_variable(env_var, resolver, fallback, monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv(env_var, '~/somewhere')
    assert resolver() == tmp_path / 'somewhere'


def test_pins_live_in_the_tools_own_config_directory(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert paths.pins_path('dectl') == tmp_path / 'dectl' / 'clisteno-shortcuts.toml'


def test_pins_filename_is_language_independent():
    """The shell reads these without knowing what the tool was written in.

    goclisteno and bashclisteno must produce this exact name, so a language
    prefix here would break every port's ability to read the others' files.
    """
    assert paths.CONFIG_SUFFIX == 'clisteno-shortcuts.toml'


def test_state_and_cache_namespace_by_library_not_by_tool(monkeypatch, tmp_path):
    """The inversion versus pins_path is deliberate — see the module docstring.

    Nesting these under the tool would put the ledger in the same directory as
    pyselfupdate's autoupdate.json, which is machine-local and must not sync.
    """
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))

    assert paths.ledger_path('dectl') == tmp_path / 'state' / 'clisteno' / 'dectl.json'
    assert paths.model_path('dectl') == tmp_path / 'cache' / 'clisteno' / 'dectl.json'
    assert paths.index_path('dectl') == tmp_path / 'cache' / 'clisteno' / 'dectl.tsv'


def test_every_tool_shares_one_state_directory(monkeypatch, tmp_path):
    """One Syncthing folder covers the fleet, however many tools adopt the library."""
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    parents = {paths.ledger_path(tool).parent for tool in ('dectl', 'forge', 'syncer')}
    assert parents == {tmp_path / 'clisteno'}


def test_model_and_index_are_distinct_files(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    assert paths.model_path('dectl') != paths.index_path('dectl')


def test_ledger_is_not_written_into_the_cache(monkeypatch, tmp_path):
    """Losing the ledger changes behaviour; losing the cache costs a recompute.

    Sharing a directory would make a cache-clearing script silently reassign
    every prefix the user has already learned.
    """
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    assert paths.ledger_path('dectl').parent != paths.model_path('dectl').parent
