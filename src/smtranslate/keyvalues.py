"""Minimal, line-aware parser for SourceMod KeyValues (SMC) files.

Unlike the ``vdf`` package, this keeps line numbers for every key and value and
preserves duplicate keys, so issues can be reported at an exact location.
"""

from dataclasses import dataclass, field
from typing import NamedTuple

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


class KVSyntaxError(Exception):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line


class Token(NamedTuple):
    kind: str  # "string", "{" or "}"
    value: str
    line: int


@dataclass
class KVNode:
    key: str
    line: int
    value: str | None = None
    children: list["KVNode"] = field(default_factory=list)

    @property
    def is_section(self) -> bool:
        return self.value is None


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    length = len(text)
    while i < length:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace() or c == "﻿":
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = length if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end == -1:
                raise KVSyntaxError("Unterminated block comment", line)
            line += text.count("\n", i, end)
            i = end + 2
        elif c in "{}":
            tokens.append(Token(c, c, line))
            i += 1
        elif c == '"':
            start_line = line
            i += 1
            value: list[str] = []
            while True:
                if i >= length:
                    raise KVSyntaxError(
                        "Unterminated string (missing closing quote?)", start_line
                    )
                c = text[i]
                if c == "\\" and i + 1 < length:
                    nxt = text[i + 1]
                    value.append(ESCAPES.get(nxt, "\\" + nxt))
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    break
                if c == "\n":
                    # Almost always a missing closing quote, use "\n" for line breaks
                    raise KVSyntaxError(
                        "Unterminated string (missing closing quote?)", start_line
                    )
                value.append(c)
                i += 1
            tokens.append(Token("string", "".join(value), start_line))
        else:
            start = i
            while (
                i < length
                and not text[i].isspace()
                and text[i] not in '{}"'
                and not text.startswith("//", i)
            ):
                i += 1
            tokens.append(Token("string", text[start:i], line))
    return tokens


def parse(text: str) -> list[KVNode]:
    """Parse KeyValues text into a list of top-level nodes (duplicates preserved)."""
    tokens = tokenize(text)
    pos = 0

    def parse_block(open_line: int | None) -> list[KVNode]:
        nonlocal pos
        nodes: list[KVNode] = []
        while True:
            if pos >= len(tokens):
                if open_line is not None:
                    raise KVSyntaxError("Unclosed '{'", open_line)
                return nodes
            key = tokens[pos]
            pos += 1
            if key.kind == "}":
                if open_line is None:
                    raise KVSyntaxError("Unexpected '}'", key.line)
                return nodes
            if key.kind == "{":
                raise KVSyntaxError("Unexpected '{' (missing section name?)", key.line)
            if pos >= len(tokens):
                raise KVSyntaxError(f'Key "{key.value}" has no value', key.line)
            value = tokens[pos]
            pos += 1
            if value.kind == "{":
                nodes.append(
                    KVNode(key.value, key.line, children=parse_block(value.line))
                )
            elif value.kind == "}":
                raise KVSyntaxError(f'Key "{key.value}" has no value', key.line)
            else:
                nodes.append(KVNode(key.value, key.line, value=value.value))

    return parse_block(None)
