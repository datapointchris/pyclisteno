import pytest
from apps import app_with_markup

from pyclisteno.assign import assign
from pyclisteno.ledger import Ledger
from pyclisteno.markup import is_tag
from pyclisteno.markup import strip_markup
from pyclisteno.model import render_index
from pyclisteno.model import render_model
from pyclisteno.walk import walk


@pytest.mark.parametrize('body', ['bold', '/bold', 'bold red', 'dim', 'green', 'i', '/'])
def test_rich_styles_are_tags(body):
    assert is_tag(body) is True


@pytest.mark.parametrize('body', ['id', 'OPTIONS', 'RUN_ID', 'env', 'alias'])
def test_the_things_a_help_row_puts_in_brackets_are_not_tags(body):
    """cli-design.md uses `[id]` for an optional argument, which must survive."""
    assert is_tag(body) is False


def test_a_tag_is_removed_and_its_text_kept():
    assert strip_markup('Glue job [bold]source-copy[/bold] → my-{env}-source-copy-job') == 'Glue job source-copy → my-{env}-source-copy-job'


def test_an_optional_argument_survives():
    assert strip_markup('Show logs [RUN_ID] for the run') == 'Show logs [RUN_ID] for the run'


def test_a_summary_with_no_markup_is_returned_as_it_was():
    assert strip_markup('List previous runs.') == 'List previous runs.'


def test_the_gap_a_removed_tag_leaves_is_closed_up():
    assert strip_markup('[bold]one[/bold]  [bold]two[/bold]') == 'one two'


def test_unclosed_or_nonsense_brackets_do_not_raise():
    assert strip_markup('a [bold thing that never closes') == 'a [bold thing that never closes'
    assert strip_markup('[]') == ''


def test_the_model_keeps_the_markup_the_index_drops():
    """A rich-aware renderer wants the tags; the shell cannot use them."""
    model = walk(app_with_markup(), 'demo')
    assign(model, Ledger(tool='demo'), {})

    assert '[bold]' in render_model(model)
    assert '[bold]' not in render_index(model)
    assert 'Copy source-copy to another environment.' in render_index(model)


def test_an_optional_argument_reaches_the_index_intact():
    model = walk(app_with_markup(), 'demo')
    assign(model, Ledger(tool='demo'), {})
    assert '[RUN_ID]' in render_index(model)
