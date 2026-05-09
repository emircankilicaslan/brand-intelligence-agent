#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))

from agent.config import settings
from agent.logging_setup import configure_logging
from agent.orchestrator import run_agent


@click.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--log-level", default="INFO", help="Logging verbosity: DEBUG, INFO, WARNING, ERROR")
def main(config_path: str, log_level: str) -> None:
    """Brand Intelligence Agent — generate a Brand DNA dossier for any fashion brand.

    CONFIG_PATH is the path to a JSON brand configuration file.
    See configs/ for examples.
    """
    configure_logging(log_level)
    try:
        pdf_path = run_agent(config_path)
        click.echo(f"\n✓ Brand DNA report saved to: {pdf_path}\n")
    except Exception as exc:
        click.echo(f"\n✗ Agent failed: {exc}\n", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
