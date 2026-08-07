import pytest
import typer
from apps import app_with
from apps import make_callback

from pyclisteno.assign import assign
from pyclisteno.fixture import build_fixture_app
from pyclisteno.ledger import Ledger
from pyclisteno.walk import walk


def prefixes(model):
    return {' '.join(node.path): node.prefix for node in model.nodes() if node.path}


def assign_app(app, ledger=None, pins=None, tool='demo'):
    model = walk(app, tool)
    saved = assign(model, ledger or Ledger(tool=tool), pins or {})
    return model, saved


def test_the_shortest_unambiguous_prefix_wins():
    model, _ = assign_app(app_with('deploy', 'status'))
    assert prefixes(model) == {'deploy': 'd', 'status': 's'}


def test_colliding_siblings_lengthen_until_they_separate():
    model, _ = assign_app(app_with('review', 'restart'))
    assert prefixes(model) == {'restart': 'res', 'review': 'rev'}


def test_a_name_that_is_a_prefix_of_a_sibling_takes_its_whole_name():
    """`run` can never be a unique prefix of itself while `runs` exists.

    With `run` holding `r`, `runs` may take neither `ru` nor `run`, because
    typing `run` would then reach `runs`.
    """
    model, _ = assign_app(app_with('run', 'runs'))
    assert prefixes(model) == {'run': 'r', 'runs': 'runs'}


def test_assignment_is_deterministic():
    first, _ = assign_app(app_with('run', 'runs', 'review'))
    second, _ = assign_app(app_with('run', 'runs', 'review'))
    assert prefixes(first) == prefixes(second)


def test_declaration_order_does_not_change_the_outcome():
    forwards, _ = assign_app(app_with('run', 'runs', 'review'))
    backwards, _ = assign_app(app_with('review', 'runs', 'run'))
    assert prefixes(forwards) == prefixes(backwards)


def test_an_incumbent_keeps_its_prefix_when_a_sibling_arrives():
    """Monotonicity: `run` alone is `r`, and adding `review` must not push it to `ru`."""
    _, ledger = assign_app(app_with('run'))
    assert ledger.assignments == {'run': 'r'}

    model, grown = assign_app(app_with('run', 'review'), ledger=ledger)

    assert prefixes(model) == {'run': 'r', 'review': 're'}
    assert grown.retired == {}


def test_a_newcomer_never_shadows_an_incumbent():
    _, ledger = assign_app(app_with('run'))
    model, _ = assign_app(app_with('run', 'runs'), ledger=ledger)
    assert prefixes(model) == {'run': 'r', 'runs': 'runs'}


def test_a_removed_commands_prefix_is_retired_rather_than_dropped():
    _, ledger = assign_app(app_with('run', 'runs'))
    _, shrunk = assign_app(app_with('run'), ledger=ledger)
    assert shrunk.assignments == {'run': 'r'}
    assert shrunk.retired == {'runs': ['runs']}


def test_a_retired_prefix_is_never_handed_to_another_command():
    """The worst failure available here is a sequence that still works and now does something else."""
    _, ledger = assign_app(app_with('run', 'runs'))
    _, shrunk = assign_app(app_with('run'), ledger=ledger)

    model, _ = assign_app(app_with('run', 'runsagain'), ledger=shrunk)

    assert prefixes(model)['runsagain'] == 'runsa'


def test_a_returning_command_gets_its_own_prefix_back():
    """Reissuing a prefix to the command that held it is the opposite of recycling."""
    _, ledger = assign_app(app_with('run', 'runs'))
    _, shrunk = assign_app(app_with('run'), ledger=ledger)

    model, restored = assign_app(app_with('run', 'runs'), ledger=shrunk)

    assert prefixes(model) == {'run': 'r', 'runs': 'runs'}
    assert restored.retired == {}


def test_a_new_prefix_may_not_be_short_enough_to_swallow_a_retired_one():
    """With `ru` retired, a new `run` cannot take `r` — typing `ru` would fall through to it."""
    _, ledger = assign_app(app_with('review', 'runs'))
    assert ledger.assignments == {'review': 're', 'runs': 'ru'}

    _, shrunk = assign_app(app_with('review'), ledger=ledger)
    model, _ = assign_app(app_with('review', 'run'), ledger=shrunk)

    assert prefixes(model)['run'] == 'run'


def test_excluded_commands_get_no_prefix():
    app = typer.Typer()
    app.command(name='deploy')(make_callback('deploy'))
    app.command(name='destroy')(make_callback('destroy', excluded=True))

    model, ledger = assign_app(app)

    assert prefixes(model) == {'deploy': 'd', 'destroy': None}
    assert 'destroy' not in ledger.assignments


def test_an_excluded_command_does_not_consume_a_prefix_from_its_siblings():
    app = typer.Typer()
    app.command(name='deploy')(make_callback('deploy'))
    app.command(name='destroy')(make_callback('destroy', excluded=True))

    model, _ = assign_app(app)

    assert prefixes(model)['deploy'] == 'd'


def test_a_source_pin_beats_the_computed_minimum():
    app = typer.Typer()
    app.callback()(lambda: None)
    app.command(name='run')(make_callback('run', pin='ru'))

    model, _ = assign_app(app)

    assert prefixes(model) == {'run': 'ru'}


def test_a_config_pin_beats_a_source_pin():
    app = typer.Typer()
    app.callback()(lambda: None)
    app.command(name='review')(make_callback('review', pin='rev'))

    model, _ = assign_app(app, pins={'review': 're'})

    assert prefixes(model) == {'review': 're'}


def test_a_pin_that_is_not_a_prefix_of_the_name_is_ignored():
    """A pin that is not a prefix is the parallel namespace the design rejects."""
    model, _ = assign_app(app_with('deploy'), pins={'deploy': 'xyz'})
    assert prefixes(model) == {'deploy': 'd'}


def test_a_pin_that_collides_falls_through_to_the_next_source():
    app = typer.Typer()
    app.command(name='run')(make_callback('run', pin='r'))
    app.command(name='review')(make_callback('review', pin='r'))

    model, _ = assign_app(app)

    assigned = prefixes(model)
    assert assigned['review'] == 'r'
    assert assigned['run'] == 'ru'


def test_a_pin_beats_an_incumbents_grandfathered_prefix():
    _, ledger = assign_app(app_with('review'))
    assert ledger.assignments == {'review': 'r'}

    model, repinned = assign_app(app_with('review'), ledger=ledger, pins={'review': 'rev'})

    assert prefixes(model) == {'review': 'rev'}
    assert repinned.retired == {'review': ['r']}


def test_a_command_with_no_prefix_left_gets_none_rather_than_breaking_the_cli():
    ledger = Ledger(tool='demo', assignments={}, retired={'gone': ['r', 'ru', 'run']})
    model, _ = assign_app(app_with('run'), ledger=ledger)
    assert prefixes(model) == {'run': None}


def test_prefixes_are_assigned_per_level_not_across_the_whole_tree():
    model, _ = assign_app(build_fixture_app(), tool='hostile')
    assigned = prefixes(model)
    assert assigned['glue nightly review'] == 're'
    assert assigned['review'] == 're'


def test_the_hostile_fixture_assigns_as_designed():
    model, _ = assign_app(build_fixture_app(), tool='hostile')
    assert prefixes(model) == {
        'destroy': None,
        'glue': 'g',
        'glue hourly': 'h',
        'glue hourly review': 're',
        'glue hourly run': 'ru',
        'glue nightly': 'n',
        'glue nightly review': 're',
        'glue nightly run': 'ru',
        'glue source-copy': 's',
        'review': 're',
        'run': 'ru',
        'runs': 'runs',
    }


@pytest.mark.parametrize('names', [('run', 'runs'), ('review', 'restart', 'run'), ('a', 'ab', 'abc'), ('x',)])
def test_no_assignment_ever_lets_one_sibling_capture_another(names):
    """The invariant, checked directly: typing any prefix of a name must reach that name.

    A sweep rather than a case, because the rule is easy to satisfy by accident
    on the examples that motivated it and hard to satisfy on the ones that did not.
    """
    model, _ = assign_app(app_with(*names))
    assigned = {node.name: node.prefix for node in model.root.children}
    for name, prefix in assigned.items():
        for length in range(len(prefix), len(name) + 1):
            typed = name[:length]
            winner = max(
                (other for other, other_prefix in assigned.items() if typed.startswith(other_prefix)),
                key=lambda other: len(assigned[other]),
            )
            assert winner == name, f'typing {typed!r} reaches {winner!r}, not {name!r}'
