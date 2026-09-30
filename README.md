# smtranslate

SourceMod translation linter. It supports both translation layouts, which can also be mixed:

- every language inline in `translations/<file>.txt`
- one subfolder per language, `translations/<langid>/<file>.txt`

## Checks

| Severity | Check |
| - | - |
| error | Syntax errors (unterminated strings, unbalanced braces, ...) and missing `"Phrases"` section |
| error | Duplicate phrases, or duplicate translations inside a phrase |
| error | Unknown language ids (not in [languages.cfg](src/smtranslate/config/languages.cfg)) |
| error | Phrase without an English (`en`) translation |
| error | Invalid `#format`, or a translation using a `{N}` parameter not declared in `#format` (SourceMod prints it as is) |
| error | A translation using the same `{N}` parameter twice (SourceMod only replaces the first one) |
| warning | Translation not using every `#format` parameter, or using `{N}` without `#format` |
| warning | Missing translations for the expected languages (see `--languages`) |
| error | Language subfolder file using another language key (e.g. `"en"` in `th/`): SourceMod loads it as that language |
| warning | Language subfolder issues: unknown folder, file or phrase not in English, `#format` key, translation also defined inline |

## GitHub Action

Add this workflow (for example `.github/workflows/translations.yml`) to any repository with translations:

```yaml
name: Translations

on:
  push:
    paths:
      - "addons/sourcemod/translations/**"
  pull_request:
    paths:
      - "addons/sourcemod/translations/**"

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: srcdslab/smtranslate@v1
```

Or add the step to an existing CI job. Issues are reported as:

- **annotations** on the workflow run and inline on the pull request diff
- a **job summary** with a table of every issue, linking to the file and line
- **step outputs** `errors` and `warnings`

If the translations folder doesn't exist, the step is skipped, so it's safe to roll out on every repository.

### Inputs

| Input | Default | Description |
| - | - | - |
| `path` | `addons/sourcemod/translations` | Translations folder |
| `languages` | `detected` | Languages every phrase must be translated to: `detected` (languages already used in the folder), `all` (every language in languages.cfg) or a comma-separated list such as `fr,ru,zho` |
| `fail-on` | `error` | Fail the step on `error`, `warning`, or `never` |
| `config-folder` | bundled | Custom folder with `config.yml` and `languages.cfg` |
| `python-version` | `3.11` | Python version used to run smtranslate |

## CLI

### Installation

```bash
git clone https://github.com/srcdslab/smtranslate.git
cd smtranslate
python -m pip install -e .
```

### Usage

```bash
smtranslate check --translation-folder addons/sourcemod/translations
smtranslate check --help
```

`--format` can be `text` (default), `markdown` or `github` (annotations, job summary and step outputs).

### Development

```bash
python -m pip install -e .[dev]
pytest
```
