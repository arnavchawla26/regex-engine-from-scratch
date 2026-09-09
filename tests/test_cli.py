import io

import pytest

from regexlib.cli import run


def _run(argv, stdin_text=None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    if stdin_text is not None:
        import sys

        old_stdin = sys.stdin
        sys.stdin = io.StringIO(stdin_text)
        try:
            code = run(argv, stdout=stdout, stderr=stderr)
        finally:
            sys.stdin = old_stdin
    else:
        code = run(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("apple 1\nbanana 22\ncherry\nDATE 2026-09-09\n")
    return str(p)


def test_basic_match_prints_matching_lines(sample_file):
    code, out, err = _run([r"\d+", sample_file])
    assert code == 0
    assert "apple 1" in out
    assert "banana 22" in out
    assert "cherry" not in out
    assert "DATE 2026-09-09" in out


def test_no_match_exit_code(sample_file):
    code, out, err = _run([r"zzzz", sample_file])
    assert code == 1
    assert out == ""


def test_ignore_case(sample_file):
    code, out, err = _run(["-i", "date", sample_file])
    assert code == 0
    assert "DATE 2026-09-09" in out


def test_invert_match(sample_file):
    code, out, err = _run(["-v", r"\d", sample_file])
    assert code == 0
    assert "cherry" in out
    assert "apple 1" not in out


def test_count(sample_file):
    code, out, err = _run(["-c", r"\d+", sample_file])
    assert code == 0
    assert out.strip() == "3"


def test_line_number(sample_file):
    code, out, err = _run(["-n", r"\d+", sample_file])
    assert code == 0
    lines = out.strip().split("\n")
    assert lines[0].startswith("1:")
    assert lines[1].startswith("2:")


def test_only_matching(sample_file):
    code, out, err = _run(["-o", r"\d+", sample_file])
    assert code == 0
    assert out.strip().split("\n") == ["1", "22", "2026", "09", "09"]


def test_stdin_used_when_no_files():
    code, out, err = _run([r"\d+"], stdin_text="a1\nb2\nnothing here\n")
    assert code == 0
    assert "a1" in out
    assert "b2" in out
    assert "nothing here" not in out


def test_backtrack_engine_flag(sample_file):
    code, out, err = _run(["--engine", "backtrack", r"\d+", sample_file])
    assert code == 0
    assert "apple 1" in out


def test_bad_pattern_exits_2():
    code, out, err = _run(["(unclosed", "/dev/null"])
    assert code == 2
    assert "bad pattern" in err


def test_missing_file_reports_error_and_exits_2():
    code, out, err = _run([r"\d+", "/no/such/file.txt"])
    assert code == 2
    assert "no/such/file.txt" in err


def test_multiple_files_prefix_label(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello 1\n")
    f2.write_text("world 2\n")
    code, out, err = _run([r"\d+", str(f1), str(f2)])
    assert code == 0
    assert f"{f1}:hello 1" in out
    assert f"{f2}:world 2" in out
