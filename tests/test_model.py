import json

import pytest

from pyclisteno.assign import assign
from pyclisteno.fixture import build_fixture_app
from pyclisteno.ledger import Ledger
from pyclisteno.model import Model
from pyclisteno.model import export
from pyclisteno.model import load_model
from pyclisteno.model import render_index
from pyclisteno.model import render_model
from pyclisteno.model import write_atomically
from pyclisteno.walk import walk


@pytest.fixture
def model():
    return walk(build_fixture_app(), 'hostile', version='1.2.3')


def test_a_model_survives_a_round_trip_through_json(model):
    assert Model.from_dict(json.loads(render_model(model))) == model


def test_a_round_trip_keeps_prefixes_that_assignment_filled_in(model):
    model.root.children[0].prefix = 'de'
    reloaded = Model.from_dict(json.loads(render_model(model)))
    assert reloaded.root.children[0].prefix == 'de'


def test_a_dump_missing_a_field_fails_rather_than_defaulting(model):
    """A silently defaulted field is a shortcut that quietly changes meaning."""
    data = model.to_dict()
    del data['root']['excluded']
    with pytest.raises(KeyError):
        Model.from_dict(data)


def test_the_index_holds_only_what_assignment_has_reached(model):
    assert render_index(model) == ''


def test_the_index_is_prefix_then_typeable_command_then_summary(model):
    find_run = next(node for node in model.nodes() if node.path == ['glue', 'nightly', 'run'])
    find_run.prefix = 'gnr'
    assert render_index(model) == 'gnr\thostile glue nightly run\tStart the job and wait for it.\n'


def test_the_index_omits_metavars_the_shell_cannot_type(model):
    """Column two goes into the buffer, and a literal `<alias>` is not a command."""
    glue = next(node for node in model.nodes() if node.path == ['glue'])
    glue.prefix = 'g'
    assert render_index(model).strip().split('\t')[1] == 'hostile glue'
    assert glue.use == 'hostile glue <alias>'


def test_every_index_row_has_exactly_three_columns(model):
    for index, node in enumerate(model.nodes()):
        node.prefix = f'p{index}'
    for line in render_index(model).splitlines():
        assert len(line.split('\t')) == 3


def test_writing_leaves_no_scratch_file_behind(tmp_path, model):
    """The shell reads these while the tool may be rewriting them."""
    destination = tmp_path / 'clisteno' / 'hostile.json'
    write_atomically(destination, render_model(model))
    assert load_model(destination) == model
    assert [path.name for path in destination.parent.iterdir()] == ['hostile.json']


def test_export_writes_both_cache_files(tmp_path, model, monkeypatch):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    model.root.children[0].prefix = 'de'

    export(model)

    assert load_model(tmp_path / 'clisteno' / 'hostile.json') == model
    assert (tmp_path / 'clisteno' / 'hostile.tsv').read_text().startswith('de\thostile destroy\t')


def test_the_index_agrees_with_the_model_it_was_written_from(tmp_path, model, monkeypatch):
    """Both files come from one walk, so a row in one and no node in the other is a bug."""
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    assign(model, Ledger(tool='hostile'), {})

    export(model)

    reloaded = load_model(tmp_path / 'clisteno' / 'hostile.json')
    rows = [line.split('\t') for line in (tmp_path / 'clisteno' / 'hostile.tsv').read_text().splitlines()]
    by_command = {' '.join([reloaded.tool, *node.path]): node for node in reloaded.nodes() if node.prefix}

    assert len(rows) == len(by_command)
    for prefix, command, summary in rows:
        assert by_command[command].prefix == prefix
        assert by_command[command].summary == summary


def test_writing_replaces_an_existing_file(tmp_path, model):
    destination = tmp_path / 'hostile.tsv'
    write_atomically(destination, 'stale\n')
    write_atomically(destination, 'fresh\n')
    assert destination.read_text() == 'fresh\n'
