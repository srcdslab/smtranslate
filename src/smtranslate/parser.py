#!/usr/bin/python3
# Copyright (c) 2023 Peace-Maker
import logging
import pathlib
import re
from dataclasses import dataclass, field

from smtranslate.classes import Phrase, PhraseFile, Report, Severity, Translation
from smtranslate.keyvalues import KVNode, KVSyntaxError, parse

logger = logging.getLogger(__name__)

PARAM_REGEX = re.compile(r"\{([0-9]+)\}")
FORMAT_REGEX = re.compile(r"\{([0-9]+):[^{}]+\}")
FORMAT_FULL_REGEX = re.compile(r"^\{[0-9]+:[^{}]+\}(,\{[0-9]+:[^{}]+\})*$")

DETECTED = "detected"
ALL = "all"


@dataclass
class Result:
    reports: list[Report] = field(default_factory=list)
    files: list[PhraseFile] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for x in self.reports if x.severity == Severity.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for x in self.reports if x.severity == Severity.WARNING)


def display_path(path: pathlib.Path) -> str:
    """Path relative to the working directory when possible (used for GitHub annotations)."""
    try:
        return path.resolve().relative_to(pathlib.Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_languages(language_cfg_path: str) -> dict[str, str]:
    nodes = parse(pathlib.Path(language_cfg_path).read_text("utf-8"))
    section = next((x for x in nodes if x.key == "Languages"), None)
    if section is None:
        raise ValueError(f'{language_cfg_path} has no "Languages" section')
    return {x.key: x.value for x in section.children if x.value is not None}


def parse_format(value: str) -> list[int] | None:
    """Return the parameter indices declared by a "#format" value, or None if invalid."""
    if not value:
        return []
    if not FORMAT_FULL_REGEX.match(value):
        return None
    return [int(x) for x in FORMAT_REGEX.findall(value)]


class Checker:
    def __init__(self, known_languages: dict[str, str]) -> None:
        self.known_languages = known_languages
        self.reports: list[Report] = []

    def report(
        self,
        severity: Severity,
        message: str,
        file: PhraseFile,
        line: int | None = None,
        langid: str | None = None,
        phrase_key: str | None = None,
    ) -> None:
        self.reports.append(
            Report(
                severity, message, file.path, line, langid or file.langid, phrase_key
            )
        )

    def language_name(self, langid: str) -> str:
        name = self.known_languages.get(langid)
        return f"{name} ({langid})" if name else langid

    def parse_file(self, file: pathlib.Path, langid: str | None) -> PhraseFile:
        logger.debug(f"Parsing {file}")
        phrase_file = PhraseFile(file.name, display_path(file), langid, [])
        try:
            nodes = parse(file.read_text("utf-8"))
        except UnicodeDecodeError as ex:
            phrase_file.error = str(ex)
            self.report(Severity.ERROR, f"File is not valid UTF-8: {ex}", phrase_file)
            return phrase_file
        except KVSyntaxError as ex:
            phrase_file.error = ex.message
            self.report(
                Severity.ERROR, f"Syntax error: {ex.message}", phrase_file, ex.line
            )
            return phrase_file

        root = next((x for x in nodes if x.key == "Phrases" and x.is_section), None)
        if root is None:
            phrase_file.error = 'Missing "Phrases" section'
            self.report(
                Severity.ERROR,
                'File does not start with a "Phrases" section',
                phrase_file,
                1,
            )
            return phrase_file

        for node in root.children:
            if not node.is_section:
                self.report(
                    Severity.ERROR,
                    f'"{node.key}" should be a phrase section, not a value',
                    phrase_file,
                    node.line,
                    phrase_key=node.key,
                )
                continue
            previous = phrase_file.get(node.key)
            if previous is not None:
                self.report(
                    Severity.ERROR,
                    f"Duplicate phrase (first defined on line {previous.line})",
                    phrase_file,
                    node.line,
                    phrase_key=node.key,
                )
                continue
            phrase_file.phrases.append(self.parse_phrase(phrase_file, node))
        return phrase_file

    def parse_phrase(self, file: PhraseFile, node: KVNode) -> Phrase:
        phrase = Phrase(node.key, node.line, None, None, [])
        for child in node.children:
            if child.value is None:
                self.report(
                    Severity.ERROR,
                    f'Unexpected section "{child.key}" inside a phrase',
                    file,
                    child.line,
                    phrase_key=phrase.key,
                )
                continue
            if child.key == "#format":
                phrase.format = Translation(child.key, child.value, child.line)
                phrase.format_params = parse_format(child.value)
                if phrase.format_params is None or sorted(phrase.format_params) != list(
                    range(1, len(phrase.format_params) + 1)
                ):
                    self.report(
                        Severity.ERROR,
                        f'Invalid "#format" value "{child.value}" (expected e.g. "{{1:s}},{{2:d}}")',
                        file,
                        child.line,
                        phrase_key=phrase.key,
                    )
                    phrase.format_params = None
                continue

            previous = phrase.get(child.key)
            if previous is not None:
                self.report(
                    Severity.ERROR,
                    f"Duplicate translation (first defined on line {previous.line})",
                    file,
                    child.line,
                    child.key,
                    phrase.key,
                )
                continue
            if child.key not in self.known_languages:
                self.report(
                    Severity.ERROR,
                    f'Unknown language "{child.key}"',
                    file,
                    child.line,
                    child.key,
                    phrase.key,
                )
            phrase.translations.append(
                Translation(
                    child.key,
                    child.value,
                    child.line,
                    {int(x) for x in PARAM_REGEX.findall(child.value)},
                )
            )
        return phrase

    def check_params(
        self,
        file: PhraseFile,
        phrase_key: str,
        translation: Translation,
        format_params: list[int] | None,
        has_format: bool,
    ) -> None:
        def fmt(params: set[int]) -> str:
            return ", ".join(f"{{{x}}}" for x in sorted(params))

        if not has_format:
            if translation.params:
                self.report(
                    Severity.WARNING,
                    f'Uses {fmt(translation.params)} but the phrase has no "#format"',
                    file,
                    translation.line,
                    translation.langid,
                    phrase_key,
                )
            return
        if format_params is None:
            # "#format" is invalid, already reported
            return

        declared = set(format_params)
        undeclared = translation.params - declared
        if undeclared:
            self.report(
                Severity.ERROR,
                f'Uses {fmt(undeclared)} but "#format" only declares {len(declared)} parameter(s)',
                file,
                translation.line,
                translation.langid,
                phrase_key,
            )
        unused = declared - translation.params
        if unused:
            self.report(
                Severity.WARNING,
                f"Does not use format parameter(s) {fmt(unused)}",
                file,
                translation.line,
                translation.langid,
                phrase_key,
            )


def run(
    *,
    language_cfg_path: str,
    translation_folder_path: str,
    languages: str = DETECTED,
) -> Result:
    """Check a SourceMod translations folder.

    Supports both layouts used by SourceMod: every language inline in
    ``translations/<file>.txt``, and one subfolder per language
    (``translations/<langid>/<file>.txt``), as well as a mix of both.

    ``languages`` selects which languages every phrase is expected to be translated to:
    ``detected`` (languages already used somewhere in the folder), ``all`` (every language
    in languages.cfg) or a comma-separated list of language ids.
    """
    logger.info("Parsing languages.cfg...")
    known_languages = load_languages(language_cfg_path)
    logger.info(f"Available languages: {len(known_languages)}")

    checker = Checker(known_languages)
    root = pathlib.Path(translation_folder_path)
    if not root.is_dir():
        raise FileNotFoundError(
            f"Translation folder not found: {translation_folder_path}"
        )

    # English (and inline translations) live at the root of the translations folder
    base_files = [
        checker.parse_file(x, None) for x in sorted(root.glob("*.txt")) if x.is_file()
    ]

    # Other languages may use a subfolder named after their language id
    lang_files: dict[str, list[PhraseFile]] = {}
    for folder in sorted(x for x in root.iterdir() if x.is_dir()):
        files = sorted(x for x in folder.glob("*.txt") if x.is_file())
        if not files:
            continue
        if folder.name not in known_languages or folder.name == "en":
            checker.reports.append(
                Report(
                    Severity.WARNING,
                    f'Folder "{folder.name}" is not a known language folder, SourceMod will not load it',
                    display_path(folder),
                )
            )
            continue
        lang_files[folder.name] = [checker.parse_file(x, folder.name) for x in files]

    # Which languages must every phrase be translated to
    if languages == DETECTED:
        expected = set(lang_files)
        for file in base_files:
            for phrase in file.phrases:
                expected.update(x.langid for x in phrase.translations)
    elif languages == ALL:
        expected = set(known_languages)
    else:
        expected = {x.strip() for x in languages.split(",") if x.strip()}
        unknown = sorted(expected - set(known_languages))
        if unknown:
            raise ValueError(
                f"Unknown language(s): {', '.join(unknown)} (see languages.cfg)"
            )
    expected = sorted((expected & set(known_languages)) - {"en"})

    # Checks on base files: English presence and parameters of inline translations
    for file in base_files:
        for phrase in file.phrases:
            if phrase.get("en") is None:
                checker.report(
                    Severity.ERROR,
                    "Missing English (en) translation",
                    file,
                    phrase.line,
                    phrase_key=phrase.key,
                )
            for translation in phrase.translations:
                checker.check_params(
                    file,
                    phrase.key,
                    translation,
                    phrase.format_params,
                    phrase.format is not None,
                )

    # Checks on language subfolders against the base files
    for langid, files in lang_files.items():
        for file in files:
            if file.error:
                continue
            base_file = next(
                (x for x in base_files if x.filename == file.filename), None
            )
            if base_file is None:
                checker.report(Severity.WARNING, "File doesn't exist in English", file)
                continue
            if not file.phrases:
                checker.report(Severity.WARNING, "File is empty", file)
                continue
            for phrase in file.phrases:
                if phrase.format:
                    checker.report(
                        Severity.WARNING,
                        'Includes a "#format" key, it belongs in the English file only',
                        file,
                        phrase.format.line,
                        phrase_key=phrase.key,
                    )
                base_phrase = base_file.get(phrase.key)
                if base_phrase is None:
                    message = "Phrase doesn't exist in English"
                    other = next((x for x in base_files if x.get(phrase.key)), None)
                    if other is not None:
                        message = f"Phrase exists in a different file in English: {other.filename}"
                    checker.report(
                        Severity.WARNING,
                        message,
                        file,
                        phrase.line,
                        phrase_key=phrase.key,
                    )
                    continue
                for translation in phrase.translations:
                    if translation.langid != langid:
                        # SourceMod only reads the folder's language from this file
                        checker.report(
                            Severity.ERROR,
                            f"Uses the {checker.language_name(translation.langid)} key in the "
                            f"{checker.language_name(langid)} folder, SourceMod will ignore it",
                            file,
                            translation.line,
                            translation.langid,
                            phrase.key,
                        )
                        continue
                    if base_phrase.get(langid) is not None:
                        checker.report(
                            Severity.WARNING,
                            f"Translation is also defined inline in {base_file.path}",
                            file,
                            translation.line,
                            phrase_key=phrase.key,
                        )
                    checker.check_params(
                        file,
                        phrase.key,
                        translation,
                        base_phrase.format_params,
                        base_phrase.format is not None,
                    )

    # Missing translations for the expected languages
    for file in base_files:
        if file.error or not file.phrases:
            continue
        for langid in expected:
            lang_file = next(
                (x for x in lang_files.get(langid, []) if x.filename == file.filename),
                None,
            )
            if lang_file is not None and lang_file.error:
                continue
            missing: list[Phrase] = []
            for phrase in file.phrases:
                if phrase.get("en") is None or phrase.get(langid) is not None:
                    continue
                lang_phrase = lang_file.get(phrase.key) if lang_file else None
                if lang_phrase is None or lang_phrase.get(langid) is None:
                    missing.append(phrase)
            if not missing:
                continue
            if len(missing) == len(file.phrases) and len(missing) > 1:
                checker.report(
                    Severity.WARNING,
                    f"No {checker.language_name(langid)} translation for any phrase",
                    file,
                    langid=langid,
                )
                continue
            for phrase in missing:
                checker.report(
                    Severity.WARNING,
                    f"Missing {checker.language_name(langid)} translation",
                    file,
                    phrase.line,
                    langid,
                    phrase.key,
                )

    all_files = base_files + [x for files in lang_files.values() for x in files]
    reports = sorted(checker.reports, key=lambda x: (x.path, x.line or 0))
    return Result(reports, all_files, ["en", *expected])
