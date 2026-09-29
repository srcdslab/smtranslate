import os
import pathlib

import pytest

from smtranslate import parser
from smtranslate.classes import Severity

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
LANGUAGES_CFG = str(
    pathlib.Path(__file__).parents[1]
    / "src"
    / "smtranslate"
    / "config"
    / "languages.cfg"
)


def check(folder: str, languages: str = parser.DETECTED) -> parser.Result:
    return parser.run(
        language_cfg_path=LANGUAGES_CFG,
        translation_folder_path=str(FIXTURES / folder),
        languages=languages,
    )


@pytest.fixture(autouse=True)
def chdir_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(FIXTURES)


def test_valid_folder() -> None:
    result = check("valid")
    assert result.reports == []
    assert result.languages == ["en", "fr"]
    assert len(result.files) == 2


def test_all_languages() -> None:
    result = check("valid", parser.ALL)
    assert result.errors == 0
    # Every file is missing every other language: one warning per language
    assert result.warnings == 31


def test_unknown_language_option() -> None:
    with pytest.raises(ValueError):
        check("valid", "fr,nope")


def test_invalid_folder() -> None:
    result = check("invalid")
    found = {
        (
            os.path.basename(x.path),
            x.line,
            x.severity,
            x.langid,
            x.phrase_key,
            x.message,
        )
        for x in result.reports
    }
    expected_errors = {
        ("broken.phrases.txt", 5, None, None, "Syntax error"),
        ("plugin.phrases.txt", 6, "en", "Welcome", 'Uses {2} but "#format"'),
        ("plugin.phrases.txt", 10, None, "Welcome", "Duplicate phrase"),
        ("plugin.phrases.txt", 14, None, "NoEnglish", "Missing English"),
        ("plugin.phrases.txt", 17, "frr", "NoEnglish", 'Unknown language "frr"'),
        ("plugin.phrases.txt", 6, "en", "NoFormat", "Uses the English (en) key"),
    }
    expected_warnings = {
        ("plugin.phrases.txt", 5, "de", "NoFormat", '"#format" key'),
        ("plugin.phrases.txt", 8, "de", "Unknown", "doesn't exist in English"),
        (
            "plugin.phrases.txt",
            7,
            "de",
            "Welcome",
            "Does not use format parameter(s) {1}",
        ),
        ("plugin.phrases.txt", 19, "fr", "NoFormat", "Missing French (fr) translation"),
        ("plugin.phrases.txt", 21, "en", "NoFormat", 'no "#format"'),
        ("xx", None, None, None, "not a known language folder"),
    }
    for expected, severity in [
        (expected_errors, Severity.ERROR),
        (expected_warnings, Severity.WARNING),
    ]:
        for name, line, langid, key, message in expected:
            assert any(
                f[0] == name
                and f[1] == line
                and f[2] == severity
                and f[3] == langid
                and f[4] == key
                and message in f[5]
                for f in found
            ), (name, line, severity, message)
    assert result.errors == len(expected_errors)
    assert result.warnings == len(expected_warnings)
