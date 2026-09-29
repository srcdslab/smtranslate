import os
from collections import defaultdict

from smtranslate.classes import Report, Severity
from smtranslate.parser import Result


def describe(report: Report) -> str:
    prefix = ""
    if report.langid:
        prefix += f"[{report.langid}] "
    if report.phrase_key:
        prefix += f'"{report.phrase_key}": '
    return prefix + report.message


def location(report: Report) -> str:
    return f"{report.path}:{report.line}" if report.line else report.path


def totals(result: Result) -> str:
    return (
        f"{result.errors} error(s), {result.warnings} warning(s) in {len(result.files)} "
        f"translation file(s) (languages: {', '.join(result.languages)})"
    )


def text(result: Result) -> str:
    lines = [
        f"{location(x)}: {x.severity.value}: {describe(x)}" for x in result.reports
    ]
    lines.append(totals(result))
    return "\n".join(lines)


def escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


def github_annotations(result: Result) -> str:
    """GitHub Actions workflow commands, shown as annotations on the run and the PR diff."""
    lines = []
    for report in result.reports:
        props = f"file={escape_property(report.path)}"
        if report.line:
            props += f",line={report.line}"
        props += f",title={escape_property('smtranslate')}"
        lines.append(
            f"::{report.severity.value} {props}::{escape_data(describe(report))}"
        )
    lines.append(totals(result))
    return "\n".join(lines)


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def file_link(path: str, line: int | None) -> str:
    """Link to the file on GitHub when running in GitHub Actions, plain text otherwise."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    sha = os.environ.get("GITHUB_SHA")
    label = str(line) if line else "-"
    if not (server and repository and sha):
        return label
    url = f"{server}/{repository}/blob/{sha}/{path}"
    if line:
        url += f"#L{line}"
    return f"[{label}]({url})"


def markdown(result: Result) -> str:
    out = ["## Translations check", ""]
    if not result.reports:
        out.append(f":white_check_mark: No issues found. {totals(result)}")
        return "\n".join(out) + "\n"

    icon = ":x:" if result.errors else ":warning:"
    out += [f"{icon} **{totals(result)}**", ""]

    by_file: dict[str, list[Report]] = defaultdict(list)
    for report in result.reports:
        by_file[report.path].append(report)

    for path, reports in by_file.items():
        errors = sum(1 for x in reports if x.severity == Severity.ERROR)
        out += [
            f"<details{' open' if errors else ''}>",
            f"<summary><code>{path}</code>: {errors} error(s), {len(reports) - errors} warning(s)</summary>",
            "",
            "| | Line | Language | Phrase | Issue |",
            "| - | - | - | - | - |",
        ]
        for report in reports:
            severity = ":x:" if report.severity == Severity.ERROR else ":warning:"
            phrase = f"`{md_escape(report.phrase_key)}`" if report.phrase_key else ""
            out.append(
                f"| {severity} | {file_link(path, report.line)} | {report.langid or ''} "
                f"| {phrase} | {md_escape(report.message)} |"
            )
        out += ["", "</details>", ""]
    return "\n".join(out)


def write_github_files(result: Result) -> None:
    """Append the markdown report to the job summary and expose counts as step outputs."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write(markdown(result) + "\n")
    outputs = os.environ.get("GITHUB_OUTPUT")
    if outputs:
        with open(outputs, "a", encoding="utf-8") as file:
            file.write(f"errors={result.errors}\nwarnings={result.warnings}\n")
