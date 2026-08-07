import click
import click.testing
import pytest
from apps import app_with
from typer.testing import CliRunner

from pyclisteno.attach import attach
from pyclisteno.fixture import build_fixture_app
from pyclisteno.ledger import key_of
from pyclisteno.teach import hint
from pyclisteno.teach import targets_for
from pyclisteno.walk import commands_by_path
from pyclisteno.walk import walk


def build_click_app():
    @click.group(help='A click app.')
    def demo():
        pass

    @demo.command(help='Ship it.')
    def deploy():
        pass

    return demo


@pytest.fixture
def stores(monkeypatch, tmp_path):
    for variable in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME'):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    return tmp_path


def help_for(app, path=()):
    return CliRunner().invoke(app, [*path, '--help']).output


def test_every_assigned_node_has_somewhere_to_write(stores):
    """The guard on deriving typer's command names rather than reimplementing them.

    If typer ever changes how a name comes off a callback, taught rows stop
    appearing and nothing else breaks — which is the kind of failure that would
    otherwise go unnoticed for months.
    """
    app = build_fixture_app()
    model = attach(app, tool='hostile')
    targets = targets_for(app)
    assert [node.path for node in model.nodes() if node.prefix and key_of(node.path) not in targets] == []


def test_a_click_tree_is_written_to_directly(stores):
    """Click commands are the objects that run, so they are their own durable target."""
    app = build_click_app()
    attach(app, tool='demo', teaching=True)
    assert '(d) Ship it.' in click.testing.CliRunner().invoke(app, ['--help']).output


def test_every_command_is_found_at_the_key_the_model_uses():
    app = build_fixture_app()
    model = walk(app, 'hostile')
    commands = commands_by_path(app)
    for node in model.nodes():
        assert ' '.join(node.path) in commands


def test_teaching_off_leaves_the_help_alone(stores):
    reference = help_for(build_fixture_app())
    enrolled = build_fixture_app()
    attach(enrolled, tool='hostile')
    assert help_for(enrolled) == reference


def test_teaching_on_puts_the_short_form_in_the_parents_listing(stores):
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    rendered = help_for(app)
    assert '(ru)' in rendered
    assert '(g)' in rendered


def test_the_hint_reaches_every_level(stores):
    """Three levels down, past the alias `glue` takes as an argument."""
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    assert '(gn) The overnight full load.' in help_for(app, ['glue', 'some-alias'])
    assert '(gnre) Read the last outcome.' in help_for(app, ['glue', 'some-alias', 'nightly'])


def test_an_excluded_command_is_shown_without_a_hint(stores):
    """`destroy` still belongs in help; what it must not have is a fast path."""
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    rendered = help_for(app)
    assert 'destroy' in rendered
    assert '(d)' not in rendered


def test_teaching_does_not_change_which_commands_exist(stores):
    plain = build_fixture_app()
    taught = build_fixture_app()
    attach(taught, tool='hostile', teaching=True)
    for name in ('run', 'runs', 'review', 'destroy', 'glue'):
        assert name in help_for(plain)
        assert name in help_for(taught)


def test_teaching_does_not_reach_a_commands_own_help_screen(stores):
    """The hint belongs where the choice is made, which is the parent's listing."""
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    assert '(ru)' not in help_for(app, ['run'])


def test_the_row_keeps_its_text_and_only_gains_the_hint(stores):
    """The summary is already the first paragraph of help, so nothing is lost writing it back."""
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    collapsed = ' '.join(help_for(app).split())

    assert '(ru) Run the thing, and keep running it until something says' in collapsed


def test_a_command_still_runs_after_being_taught(stores):
    app = build_fixture_app()
    attach(app, tool='hostile', teaching=True)
    assert CliRunner().invoke(app, ['run']).exit_code == 0


def test_the_hint_avoids_the_brackets_the_grammar_already_uses():
    """`<id>` and `[id]` mean required and optional in a help row."""
    rendered = hint('ru', 'Run the thing.')
    assert rendered == '(ru) Run the thing.'
    assert '[' not in rendered


def test_teaching_a_tree_with_nothing_assigned_is_harmless(stores):
    app = app_with('run')
    reference = help_for(app)
    attach(app_with('run'), tool='demo', teaching=True)
    assert help_for(app) == reference
