import json

from apps import app_with

from pyclisteno import paths
from pyclisteno.assign import assign
from pyclisteno.ledger import Ledger
from pyclisteno.ledger import key_of
from pyclisteno.ledger import load_ledger
from pyclisteno.ledger import name_of
from pyclisteno.ledger import parent_key_of
from pyclisteno.ledger import render_ledger
from pyclisteno.ledger import save_ledger
from pyclisteno.walk import walk


def test_a_path_is_keyed_by_its_tokens_joined():
    assert key_of(['glue', 'nightly', 'run']) == 'glue nightly run'
    assert key_of([]) == ''


def test_a_key_splits_back_into_a_parent_and_a_name():
    assert parent_key_of('glue nightly run') == 'glue nightly'
    assert name_of('glue nightly run') == 'run'


def test_a_top_level_command_belongs_to_the_root():
    assert parent_key_of('run') == ''
    assert name_of('run') == 'run'


def test_a_ledger_survives_a_round_trip_through_json():
    ledger = Ledger(tool='demo', assignments={'run': 'r'}, retired={'runs': ['runs', 'ru']})
    assert Ledger.from_dict(json.loads(render_ledger(ledger))) == ledger


def test_a_tool_with_no_ledger_yet_starts_empty(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    assert load_ledger('demo') == Ledger(tool='demo')


def test_a_saved_ledger_reloads_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    model = walk(app_with('run', 'runs'), 'demo')
    ledger = assign(model, Ledger(tool='demo'), {})

    save_ledger(ledger)

    assert load_ledger('demo') == ledger
    assert paths.ledger_path('demo').exists()


def test_a_ledger_written_across_two_runs_grandfathers_the_first(monkeypatch, tmp_path):
    """The whole reason this is state and not cache."""
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    save_ledger(assign(walk(app_with('run'), 'demo'), load_ledger('demo'), {}))

    grown = walk(app_with('run', 'review'), 'demo')
    save_ledger(assign(grown, load_ledger('demo'), {}))

    assert load_ledger('demo').assignments == {'run': 'r', 'review': 're'}


def test_every_tool_keeps_its_own_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    save_ledger(Ledger(tool='alpha', assignments={'run': 'r'}))
    save_ledger(Ledger(tool='beta', assignments={'run': 'ru'}))

    assert load_ledger('alpha').assignments == {'run': 'r'}
    assert load_ledger('beta').assignments == {'run': 'ru'}
