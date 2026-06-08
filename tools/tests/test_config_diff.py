from forgejo_tools.config_diff import ForgejoConfigDiff


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_version():
    cfg = ForgejoConfigDiff(".")
    assert cfg.parse_version("forgejo-v7.0.1.clean.ini") == (7, 0, 1)
    assert cfg.parse_version("ohne-version.ini") is None


def test_read_active_and_commented_keys(tmp_path):
    cfg = ForgejoConfigDiff(str(tmp_path))
    f = _write(tmp_path, "v7.0.0.ini", "[server]\nROOT_URL = http://a\n;HTTP_PORT = 3000\n")
    parsed = cfg.read_ini_with_comments(f)
    assert parsed["server"]["ROOT_URL"] == ("http://a", False)
    assert parsed["server"]["HTTP_PORT"] == ("3000", True)


def test_read_commented_section_header(tmp_path):
    # Forgejo kommentiert ganze Sektionen aus – der Key muss trotzdem
    # unter der richtigen Sektion landen, nicht im globalen Bereich.
    cfg = ForgejoConfigDiff(str(tmp_path))
    f = _write(tmp_path, "v7.0.0.ini", ";[mailer]\n;ENABLED = false\n")
    parsed = cfg.read_ini_with_comments(f)
    assert parsed["mailer"]["ENABLED"] == ("false", True)
    assert "ENABLED" not in parsed["__global__"]


def test_value_change_is_reported(tmp_path, capsys):
    cfg = ForgejoConfigDiff(str(tmp_path))
    _write(tmp_path, "forgejo-v7.0.0.ini", "[server]\nHTTP_PORT = 3000\n")
    _write(tmp_path, "forgejo-v7.0.1.ini", "[server]\nHTTP_PORT = 3001\n")
    cfg.run()
    out = capsys.readouterr().out
    assert "[server]" in out
    assert "3000" in out and "3001" in out


def test_added_and_removed_keys(tmp_path, capsys):
    cfg = ForgejoConfigDiff(str(tmp_path))
    _write(tmp_path, "forgejo-v7.0.0.ini", "[server]\nOLD = 1\n")
    _write(tmp_path, "forgejo-v7.0.1.ini", "[server]\nNEW = 2\n")
    cfg.run()
    out = capsys.readouterr().out
    assert "NEW = 2" in out
    assert "OLD = 1" in out


def test_no_output_when_identical(tmp_path, capsys):
    cfg = ForgejoConfigDiff(str(tmp_path))
    _write(tmp_path, "forgejo-v7.0.0.ini", "[server]\nHTTP_PORT = 3000\n")
    _write(tmp_path, "forgejo-v7.0.1.ini", "[server]\nHTTP_PORT = 3000\n")
    cfg.run()
    out = capsys.readouterr().out
    assert out.strip() == ""


def test_minor_diff_only_from_last_patch(tmp_path, capsys):
    # 7.0.0 -> 7.0.1 (Patch), 7.0.1 -> 7.1.0 (Minor). Es darf KEIN
    # direkter 7.0.0 -> 7.1.0 Diff erzeugt werden.
    cfg = ForgejoConfigDiff(str(tmp_path))
    _write(tmp_path, "forgejo-v7.0.0.ini", "[a]\nK = 1\n")
    _write(tmp_path, "forgejo-v7.0.1.ini", "[a]\nK = 2\n")
    _write(tmp_path, "forgejo-v7.1.0.ini", "[a]\nK = 3\n")
    cfg.run()
    out = capsys.readouterr().out
    assert "forgejo-v7.0.0.ini -> forgejo-v7.0.1.ini" in out
    assert "forgejo-v7.0.1.ini -> forgejo-v7.1.0.ini" in out
    assert "forgejo-v7.0.0.ini -> forgejo-v7.1.0.ini" not in out
