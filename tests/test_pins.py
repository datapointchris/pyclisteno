import pytest

from pyclisteno import paths
from pyclisteno.pins import load_pins


@pytest.fixture
def pin_file(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    path = paths.pins_path('demo')
    path.parent.mkdir(parents=True)
    return path


def test_no_pin_file_means_no_pins(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert load_pins('demo') == {}


def test_pins_are_read_by_path_and_prefix(pin_file):
    pin_file.write_text('[shortcuts]\nrun = "ru"\n"glue nightly" = "ni"\n')
    assert load_pins('demo') == {'run': 'ru', 'glue nightly': 'ni'}


def test_a_broken_pin_file_costs_the_pins_not_the_cli(pin_file):
    """A tool that dies on a typo in an optional config file is a tool this library broke."""
    pin_file.write_text('[shortcuts\nrun = ru\n')
    assert load_pins('demo') == {}


def test_a_shortcuts_table_of_the_wrong_shape_is_ignored(pin_file):
    pin_file.write_text('shortcuts = "ru"\n')
    assert load_pins('demo') == {}


def test_a_file_without_a_shortcuts_table_is_ignored(pin_file):
    pin_file.write_text('[other]\nrun = "ru"\n')
    assert load_pins('demo') == {}


def test_a_pin_that_is_not_a_string_is_dropped_without_taking_the_others(pin_file):
    pin_file.write_text('[shortcuts]\nrun = 3\nreview = "re"\n')
    assert load_pins('demo') == {'review': 're'}
