import pytest

from smtranslate.keyvalues import KVSyntaxError, parse


def test_parse_keeps_lines_and_duplicates() -> None:
    nodes = parse(
        '"Phrases"\n{\n\t"a" // comment\n\t{\n\t\t"en" "x \\"y\\""\n\t}\n\t"a" { }\n}\n'
    )
    assert len(nodes) == 1
    root = nodes[0]
    assert root.key == "Phrases" and root.line == 1
    assert [(x.key, x.line) for x in root.children] == [("a", 3), ("a", 7)]
    assert root.children[0].children[0].value == 'x "y"'
    assert root.children[0].children[0].line == 5


@pytest.mark.parametrize(
    ("text", "line", "message"),
    [
        ('"Phrases"\n{\n\t"a"\n\t{\n\t\t"en" "oops\n\t}\n}', 5, "Unterminated string"),
        ('"Phrases"\n{\n\t"a"\n\t{\n', 4, "Unclosed '{'"),
        ('"Phrases"\n{\n}\n}', 4, "Unexpected '}'"),
        ('"Phrases"\n{\n\t"a"\n}', 3, "has no value"),
    ],
)
def test_syntax_errors(text: str, line: int, message: str) -> None:
    with pytest.raises(KVSyntaxError) as exc:
        parse(text)
    assert exc.value.line == line
    assert message in exc.value.message
