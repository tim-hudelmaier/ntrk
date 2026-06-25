from ntrk import config


def test_defaults_without_config(tmp_path):
    c = config.load(tmp_path)
    assert "-i" in c.input_flags and "--input" in c.input_flags
    assert "-o" in c.output_flags and "--output" in c.output_flags


def test_config_merges_on_top_of_defaults(tmp_path):
    (tmp_path / "ntrk.toml").write_text(
        '[flags]\ninputs = ["--source"]\noutputs = ["--dest"]\n'
    )
    c = config.load(tmp_path)
    # defaults still present
    assert "-i" in c.input_flags
    assert "-o" in c.output_flags
    # extensions added
    assert "--source" in c.input_flags
    assert "--dest" in c.output_flags
