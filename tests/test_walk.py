import click
import pytest
import typer
from typer.testing import CliRunner

from pyclisteno.fixture import build_fixture_app
from pyclisteno.marks import SHORTCUT_ATTRIBUTE
from pyclisteno.marks import no_shortcut
from pyclisteno.walk import as_command
from pyclisteno.walk import walk


@pytest.fixture
def model():
    return walk(build_fixture_app(), 'hostile', version='1.2.3')


def find(model, *path):
    for node in model.nodes():
        if node.path == list(path):
            return node
    raise AssertionError(f'no node at {list(path)} in {[node.path for node in model.nodes()]}')


def test_the_root_is_the_tool_itself(model):
    assert model.root.path == []
    assert model.root.name == 'hostile'
    assert model.root.kind == 'group'
    assert model.root.use == 'hostile'


def test_the_model_carries_the_tool_and_its_version(model):
    assert model.tool == 'hostile'
    assert model.tool_version == '1.2.3'
    assert model.schema == 1


def test_a_runtime_built_subtree_is_walked_like_any_other():
    """The jobs arrive from a dict, mirroring how dectl's aliases arrive from config.

    This is the case decorators cannot reach, and the reason enrollment is one
    call after the tree is built rather than a decorator per command.
    """
    model = walk(build_fixture_app(), 'hostile')
    assert find(model, 'glue', 'nightly', 'run').kind == 'command'
    assert find(model, 'glue', 'hourly', 'review').summary == 'Read the last outcome.'


def test_a_group_that_takes_an_argument_shows_it_in_the_invocation(model):
    glue = find(model, 'glue')
    assert glue.kind == 'group'
    assert glue.takes_argument is True
    assert glue.use == 'hostile glue <alias>'


def test_a_verb_that_takes_nothing_is_marked_as_such(model):
    assert find(model, 'run').takes_argument is False


def test_hyphenated_names_survive_the_walk(model):
    assert find(model, 'glue', 'source-copy').name == 'source-copy'


def test_no_shortcut_excludes_a_node_without_removing_it(model):
    """The destructive verb has to stay in the dump — help still renders it."""
    destroy = find(model, 'destroy')
    assert destroy.excluded is True
    assert all(node.excluded is False for node in model.nodes() if node.path != ['destroy'])


def test_a_pin_survives_typers_rebuild_of_the_callback():
    """typer does not hand click the function you decorated — it wraps it.

    `functools.update_wrapper` copies `__dict__`, which is the only reason a mark
    set under `@app.command()` is still readable afterwards. If typer ever stops
    wrapping this way, every pin silently stops applying, so the assumption is
    pinned here rather than left implicit.
    """
    command = as_command(build_fixture_app())
    run = command.get_command(command.context_class(command, info_name='hostile'), 'run')
    assert getattr(run.callback, SHORTCUT_ATTRIBUTE) == 'ru'


def test_hidden_commands_are_not_part_of_the_grammar(model):
    """Letting one consume a prefix would lengthen a visible sibling's for nothing."""
    assert [node.path for node in model.nodes() if 'debug-dump' in node.path] == []


def test_summaries_are_never_truncated(model):
    """Click cuts short help at 45 characters and typer's completion at 50."""
    summary = find(model, 'run').summary
    assert summary == 'Run the thing, and keep running it until something says otherwise.'
    assert len(summary) > 50


def test_summaries_are_a_single_clean_line(model):
    """The index is a TSV read straight into a zsh assoc array."""
    for node in model.nodes():
        assert '\t' not in node.summary
        assert '\n' not in node.summary
        assert '\x08' not in node.summary


def test_the_export_assigns_no_prefixes(model):
    """Assignment is a separate pass with its own ledger and precedence rules."""
    assert all(node.prefix is None for node in model.nodes())


def test_walking_does_not_disturb_the_app():
    """The library's whole proposition is that a CLI behaves identically with it."""
    runner = CliRunner()
    app = build_fixture_app()
    before = runner.invoke(app, ['--help'])
    walk(app, 'hostile')
    after = runner.invoke(app, ['--help'])
    assert before.output == after.output
    assert before.exit_code == after.exit_code


def build_click_app():
    """A plain click app, to prove the walk is not typer-specific."""

    @click.group(help='A click app.')
    def demo():
        pass

    @demo.command(help='Ship it.')
    @click.argument('target')
    @click.argument('window', required=False)
    @click.argument('extra_flags', nargs=-1)
    def deploy(target, window, extra_flags):
        pass

    @demo.command(help='Undo it.')
    @no_shortcut
    def rollback():
        pass

    return demo


def test_a_plain_click_app_walks_without_conversion():
    model = walk(build_click_app(), 'demo')
    assert model.root.kind == 'group'
    assert find(model, 'deploy').summary == 'Ship it.'
    assert find(model, 'rollback').excluded is True


def test_required_optional_and_variadic_arguments_each_get_their_own_bracket():
    assert find(walk(build_click_app(), 'demo'), 'deploy').use == 'demo deploy <target> [window] <extra-flags>...'


def test_siblings_are_ordered_by_name_whatever_order_they_were_declared():
    """Click sorts its commands, typer keeps declaration order, and assignment reads siblings in order."""
    app = typer.Typer()

    @app.command()
    def zebra():
        """Last alphabetically, first declared."""

    @app.command()
    def alpha():
        """First alphabetically, last declared."""

    assert [node.name for node in walk(app, 'demo').root.children] == ['alpha', 'zebra']


def test_walking_something_that_is_not_a_command_fails_loudly():
    with pytest.raises(TypeError, match='cannot walk'):
        walk(object(), 'demo')
