from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Translation:
    langid: str
    translation: str
    line: int
    params: set[int] = field(default_factory=set)


@dataclass
class Phrase:
    key: str
    line: int
    format: Translation | None
    format_params: list[int] | None
    translations: list[Translation]

    def get(self, langid: str) -> Translation | None:
        return next((x for x in self.translations if x.langid == langid), None)


@dataclass
class PhraseFile:
    filename: str
    path: str
    langid: str | None
    phrases: list[Phrase]
    error: str | None = None

    def get(self, key: str) -> Phrase | None:
        return next((x for x in self.phrases if x.key == key), None)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Report:
    severity: Severity
    message: str
    path: str
    line: int | None = None
    langid: str | None = None
    phrase_key: str | None = None
