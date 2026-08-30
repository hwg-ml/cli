"""
HWG-ML CLI - Main command line interface.
"""

import click

from hwg_ml_cli.commands import update_exercises, update_lectures
from hwg_ml_cli.config import DEFAULT_COURSE


@click.group()
def cli():
    """Utility commands for HWG-ML."""
    pass


@cli.group()
def exercises():
    """Manage course exercises."""
    pass


@cli.group()
def lectures():
    """Manage course lectures."""
    pass


@exercises.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="exercises",
    help="Output directory for exercises",
)
@click.option(
    "--course",
    "-c",
    type=str,
    default=DEFAULT_COURSE,
    help="Course name or slug to filter exercises",
)
def update(output, course):
    """Download new exercises from the H4HN CMS API."""
    return update_exercises(output, course)


@lectures.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="lectures",
    help="Output directory for lecture slides",
)
@click.option(
    "--course",
    "-c",
    type=str,
    default=DEFAULT_COURSE,
    help="Course name or slug to filter lectures",
)
def update(output, course):
    """Download lecture slides from the H4HN CMS API."""
    return update_lectures(output, course)


if __name__ == "__main__":
    cli()
