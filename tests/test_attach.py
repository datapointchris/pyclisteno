import sys
from pathlib import Path

import pytest
import typer
from apps import app_with
from typer.testing import CliRunner

from pyclisteno import paths
from pyclisteno.attach import DEBUG_VARIABLE
from pyclisteno.attach import attach
from pyclisteno.attach import infer_tool
from pyclisteno.fixture import build_fixture_app
from pyclisteno.ledger import load_ledger
from pyclisteno.model import load_model
from pyclisteno.walk import as_command
from pyclisteno.walk import walk


@pytest.fixture
def stores(monkeypatch, tmp_path):
    for variable in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME'):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    return tmp_path


def test_attaching_publishes_the_model_the_index_and_the_ledger(stores):
    attach(build_fixture_app(), tool='hostile')

    assert load_model(paths.model_path('hostile')).tool == 'hostile'
    assert paths.index_path('hostile').read_text().startswith('g\thostile glue\t')
    assert load_ledger('hostile').assignments['runs'] == 'runs'


def test_attaching_returns_the_assigned_model(stores):
    model = attach(build_fixture_app(), tool='hostile')
    assert {node.name: node.prefix for node in model.root.children if node.prefix} == {
        'glue': 'g',
        'review': 're',
        'run': 'ru',
        'runs': 'runs',
    }


def test_a_second_attach_leaves_every_file_untouched(stores):
    """The ledger is synced, and an identical rewrite still wakes Syncthing."""
    attach(build_fixture_app(), tool='hostile')
    written = {
        path: path.stat().st_mtime_ns for path in (paths.model_path('hostile'), paths.index_path('hostile'), paths.ledger_path('hostile'))
    }

    attach(build_fixture_app(), tool='hostile')

    assert {path: path.stat().st_mtime_ns for path in written} == written


def test_a_changed_tree_is_republished(stores):
    attach(app_with('run'), tool='demo')
    attach(app_with('run', 'review'), tool='demo')
    assert load_ledger('demo').assignments == {'run': 'r', 'review': 're'}


def test_a_pin_file_is_picked_up_without_the_tree_changing(stores):
    attach(app_with('review', 'status'), tool='demo')
    assert load_ledger('demo').assignments['review'] == 'r'

    pins = paths.pins_path('demo')
    pins.parent.mkdir(parents=True, exist_ok=True)
    pins.write_text('[shortcuts]\nreview = "rev"\n')
    attach(app_with('review', 'status'), tool='demo')

    assert load_ledger('demo').assignments['review'] == 'rev'
    assert load_ledger('demo').retired == {'review': ['r']}


def test_an_unnamed_app_falls_back_to_the_invoked_script(stores):
    """What the user types, which under pytest is pytest."""
    invoked = Path(sys.argv[0]).name
    assert infer_tool(as_command(build_fixture_app())) == invoked
    assert infer_tool(as_command(app_with('run'))) == invoked


def test_a_named_app_keeps_its_own_name(stores):
    app = typer.Typer(name='dectl')
    app.callback()(lambda: None)
    app.command(name='run')(lambda: None)

    assert infer_tool(as_command(app)) == 'dectl'


def test_a_failure_costs_enrollment_and_nothing_else(stores):
    """A tool that dies because a cache directory is read-only is a tool this library broke."""
    assert attach(object(), tool='demo') is None
    assert not paths.model_path('demo').exists()


def test_a_failure_is_visible_when_asked_for(stores, monkeypatch):
    monkeypatch.setenv(DEBUG_VARIABLE, '1')
    with pytest.raises(TypeError):
        attach(object(), tool='demo')


def test_an_unwritable_cache_does_not_reach_the_caller(stores, monkeypatch):
    blocked = stores / 'a-file-where-a-directory-should-be'
    blocked.write_text('')
    monkeypatch.setenv('XDG_CACHE_HOME', str(blocked / 'cache'))
    assert attach(build_fixture_app(), tool='hostile') is None


def every_path(model):
    return [node.path for node in model.nodes()]


def invoke_everything(app, model):
    """Every command at every level, bare and with --help."""
    runner = CliRunner()
    results = {}
    for path in every_path(model):
        for arguments in ([*path], [*path, '--help']):
            result = runner.invoke(app, arguments)
            results[tuple(arguments)] = (result.output, result.exit_code)
    return results


def test_attaching_does_not_change_a_single_byte_the_cli_produces(stores):
    """The regression test for the one constraint that is otherwise a hope.

    Every command at every level, bare and with --help, run with and without
    enrollment. Without this, "it must not disturb the CLI otherwise" is a claim
    nobody checks.
    """
    reference = build_fixture_app()
    model = walk(reference, 'hostile')
    before = invoke_everything(reference, model)

    enrolled = build_fixture_app()
    attach(enrolled, tool='hostile')
    after = invoke_everything(enrolled, model)

    assert after == before


def test_the_commands_actually_ran_rather_than_all_failing_alike(stores):
    """A suite where everything errors identically would pass the test above."""
    model = walk(build_fixture_app(), 'hostile')
    results = invoke_everything(build_fixture_app(), model)
    assert results[('run',)][1] == 0
    assert 'source-copy' in results[('glue', '--help')][0]
