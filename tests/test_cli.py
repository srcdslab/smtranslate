import pathlib

import pytest
from click.testing import CliRunner

from smtranslate.cli import cli

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("folder", "fail_on", "exit_code"),
    [
        ("valid", "error", 0),
        ("invalid", "error", 1),
        ("invalid", "never", 0),
    ],
)
def test_exit_code(folder: str, fail_on: str, exit_code: int) -> None:
    result = CliRunner().invoke(
        cli,
        ["check", "--translation-folder", str(FIXTURES / folder), "--fail-on", fail_on],
    )
    assert result.exit_code == exit_code, result.output


def test_github_format(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    outputs = tmp_path / "outputs.txt"
    monkeypatch.chdir(FIXTURES)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "srcdslab/example")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    result = CliRunner().invoke(
        cli,
        [
            "check",
            "--translation-folder",
            "invalid",
            "--format",
            "github",
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        "::error file=invalid/plugin.phrases.txt,line=6,title=smtranslate::"
        '[en] "Welcome": Uses {2} but "#format" only declares 1 parameter(s)'
    ) in result.output
    assert "::warning file=invalid/xx,title=smtranslate::" in result.output
    assert outputs.read_text() == "errors=6\nwarnings=6\n"
    markdown = summary.read_text(encoding="utf-8")
    assert (
        "https://github.com/srcdslab/example/blob/abc123/invalid/plugin.phrases.txt#L6"
        in markdown
    )
