from ntrk import config
from ntrk.parse import parse


def cfg():
    return config.Config(config.DEFAULT_INPUT_FLAGS, config.DEFAULT_OUTPUT_FLAGS)


def test_defaults_short_flags():
    p = parse(["python", "main.py", "-i", "in.csv", "-o", "out.csv"], cfg())
    assert p.inputs == ["in.csv"]
    assert p.outputs == ["out.csv"]
    assert p.script == "main.py"


def test_long_flags():
    p = parse(["main.py", "--input", "a", "--output", "b"], cfg())
    assert p.inputs == ["a"]
    assert p.outputs == ["b"]


def test_equals_form_is_self_contained():
    p = parse(["t.py", "--input=a,b", "positional", "-o", "x"], cfg())
    # '=' form comma-splits but does NOT consume 'positional'
    assert p.inputs == ["a", "b"]
    assert p.outputs == ["x"]


def test_greedy_space_list():
    p = parse(["m.py", "-i", "a", "b", "c", "-o", "x"], cfg())
    assert p.inputs == ["a", "b", "c"]
    assert p.outputs == ["x"]


def test_comma_list_split():
    p = parse(["m.py", "-i", "a,b", "-o", "x,y"], cfg())
    assert p.inputs == ["a", "b"]
    assert p.outputs == ["x", "y"]


def test_consumption_stops_at_next_flag():
    p = parse(["m.py", "-i", "a", "b", "--verbose", "-o", "x"], cfg())
    assert p.inputs == ["a", "b"]
    assert p.outputs == ["x"]


def test_repeated_flags_accumulate():
    p = parse(["m.py", "-i", "a", "-i", "b", "-o", "x", "-o", "y"], cfg())
    assert p.inputs == ["a", "b"]
    assert p.outputs == ["x", "y"]


def test_flag_with_no_value_is_empty():
    p = parse(["m.py", "-i", "-o", "x"], cfg())
    assert p.inputs == []
    assert p.outputs == ["x"]


def test_config_added_flags():
    c = config.Config(
        list(config.DEFAULT_INPUT_FLAGS) + ["--source"],
        list(config.DEFAULT_OUTPUT_FLAGS) + ["--dest"],
    )
    p = parse(["run.py", "--source", "s.csv", "--dest", "d.csv"], c)
    assert p.inputs == ["s.csv"]
    assert p.outputs == ["d.csv"]


def test_script_detection_by_interpreter_when_no_ext():
    # no source extension anywhere -> first non-flag after interpreter
    p = parse(["bash", "runme", "-i", "a"], cfg())
    assert p.script == "runme"
