import logging
import os
import sys
from typing import Any

import click
import yaml

from smtranslate import output, parser

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FOLDER = os.path.join(os.path.dirname(__file__), "config")
DEFAULT_LOGGING: dict[str, Any] = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)s | %(message)s",
    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
}


@click.group()
@click.version_option()
def cli() -> None:
    pass


@cli.command("check")
@click.option(
    "--config-folder",
    default=DEFAULT_CONFIG_FOLDER,
    show_default="bundled config",
    help="Configuration folder path (config.yml and languages.cfg).",
)
@click.option(
    "--translation-folder", required=True, help="Sourcemod translations folder path"
)
@click.option(
    "--languages",
    default=parser.DETECTED,
    show_default=True,
    help='Languages every phrase must be translated to: "detected" (languages already '
    'used in the folder), "all" (every language in languages.cfg) or a comma-separated '
    "list of language ids.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "markdown", "github"]),
    default="text",
    show_default=True,
    help='Output format. "github" emits annotations and writes the job summary and step '
    "outputs when running in GitHub Actions.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning", "never"]),
    default="error",
    show_default=True,
    help="Exit with a non-zero status when issues of this severity (or worse) are found.",
)
@click.version_option()
def check(
    config_folder: str,
    translation_folder: str,
    languages: str,
    output_format: str,
    fail_on: str,
) -> None:
    config_folder_path = os.path.abspath(config_folder)
    config_file_path = os.path.join(config_folder_path, "config.yml")

    config: dict[str, Any] = {}
    try:
        with open(config_file_path, "r") as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError:
        pass
    except yaml.YAMLError as exc:
        logger.error(sys._getframe().f_code.co_name + " " + str(exc))
        sys.exit(1)

    logging_config = {**DEFAULT_LOGGING, **config.get("logging", {})}
    logging.basicConfig(
        level=logging.getLevelName(logging_config["level"]),
        format=logging_config["format"],
        datefmt=logging_config["datefmt"],
        stream=sys.stderr,
    )

    try:
        result = parser.run(
            language_cfg_path=os.path.join(config_folder_path, "languages.cfg"),
            translation_folder_path=os.path.abspath(translation_folder),
            languages=languages,
        )
    except (OSError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(2)

    if output_format == "markdown":
        click.echo(output.markdown(result))
    elif output_format == "github":
        click.echo(output.github_annotations(result))
        output.write_github_files(result)
    else:
        click.echo(output.text(result))

    if (fail_on == "error" and result.errors) or (
        fail_on == "warning" and result.reports
    ):
        sys.exit(1)
