import pytest
from apps import app_with

from pyclisteno.assign import assign
from pyclisteno.fixture import build_fixture_app
from pyclisteno.ledger import Ledger
from pyclisteno.resolve import expand
from pyclisteno.resolve import resolve
from pyclisteno.walk import walk


@pytest.fixture
def hostile():
    model = walk(build_fixture_app(), 'hostile')
    assign(model, Ledger(tool='hostile'), {})
    return model


@pytest.mark.parametrize(
    ('typed', 'expanded'),
    [
        (['re'], ['hostile', 'review']),
        (['ru'], ['hostile', 'run']),
        (['run'], ['hostile', 'run']),
        (['review'], ['hostile', 'review']),
        (['runs'], ['hostile', 'runs']),
        (['g'], ['hostile', 'glue']),
    ],
)
def test_longest_match_reaches_the_command_that_was_typed(hostile, typed, expanded):
    assert expand(hostile, typed) == expanded


def test_a_sequence_expands_one_prefix_per_level(hostile):
    assert expand(hostile, ['g', 'n', 'ru']) == ['hostile', 'glue', 'nightly', 'run']


def test_typing_the_whole_thing_reaches_the_same_place(hostile):
    assert expand(hostile, ['glue', 'nightly', 'run']) == ['hostile', 'glue', 'nightly', 'run']


def test_a_genuinely_ambiguous_token_reaches_nothing(hostile):
    """`r` fits review, run and runs, and answering it with any of them is a coin toss."""
    assert expand(hostile, ['r']) == ['hostile', 'r']


def test_arguments_after_the_command_are_handed_back(hostile):
    assert expand(hostile, ['g', 'n', 'ru', 'yesterday']) == ['hostile', 'glue', 'nightly', 'run', 'yesterday']


def test_an_unknown_token_stops_the_walk_without_swallowing_it(hostile):
    resolution = resolve(hostile, ['g', 'zzz', 'more'])
    assert resolution.node.path == ['glue']
    assert resolution.remainder == ['zzz', 'more']


def test_an_excluded_command_is_unreachable(hostile):
    """`destroy` is in the dump and has no prefix, so nothing typed can arrive at it."""
    assert expand(hostile, ['d']) == ['hostile', 'd']
    assert expand(hostile, ['destroy']) == ['hostile', 'destroy']


def test_a_retired_sequence_resolves_to_nothing_rather_than_to_something_else():
    """The failure this whole rule exists to prevent: a sequence that still works, differently."""
    model = walk(app_with('review', 'runs'), 'demo')
    ledger = assign(model, Ledger(tool='demo'), {})
    assert ledger.assignments == {'review': 're', 'runs': 'ru'}

    shrunk_model = walk(app_with('review'), 'demo')
    shrunk = assign(shrunk_model, ledger, {})

    resolution = resolve(shrunk_model, ['ru'], shrunk)
    assert resolution.retired == 'ru'
    assert resolution.node.path == []


def test_a_retired_sequence_does_not_block_a_live_command_that_extends_it():
    """`re` still reaches review even though `ru` is a dead end beside it."""
    model = walk(app_with('review', 'runs'), 'demo')
    ledger = assign(model, Ledger(tool='demo'), {})
    shrunk_model = walk(app_with('review'), 'demo')
    shrunk = assign(shrunk_model, ledger, {})

    assert expand(shrunk_model, ['re'], shrunk) == ['demo', 'review']
    assert expand(shrunk_model, ['review'], shrunk) == ['demo', 'review']


def test_a_live_prefix_longer_than_a_retired_one_still_wins():
    """Retirement stops a sequence, it does not shadow a command that out-matches it."""
    model = walk(app_with('review', 'runs'), 'demo')
    ledger = assign(model, Ledger(tool='demo'), {})
    grown_model = walk(app_with('review', 'run'), 'demo')
    grown = assign(grown_model, assign(walk(app_with('review'), 'demo'), ledger, {}), {})

    assert expand(grown_model, ['run'], grown) == ['demo', 'run']
    assert resolve(grown_model, ['ru'], grown).retired == 'ru'


def test_resolving_without_a_ledger_uses_live_prefixes_alone(hostile):
    assert expand(hostile, ['ru'], None) == ['hostile', 'run']
