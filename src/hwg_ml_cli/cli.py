"""
HWG-ML CLI - Main command line interface.
"""

import sys
import click
import requests

from hwg_ml_cli.commands import update_exercises, update_lectures
from hwg_ml_cli.config import (
    DEFAULT_COURSE,
    DEFAULT_SUBMISSION_SERVER,
    get_submission_token,
    set_submission_token,
    get_submission_server,
    set_submission_server,
)
from hwg_ml_cli.submit import submit_file


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


@cli.group()
def config():
    """Manage CLI configuration."""
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


@config.command()
@click.option(
    "--token",
    "-t",
    required=True,
    help="Access token for authentication",
)
@click.option(
    "--server",
    "-s",
    default=DEFAULT_SUBMISSION_SERVER,
    help="Submission server URL",
)
def init(token, server):
    """Initialize submission configuration with your token."""
    set_submission_token(token)
    set_submission_server(server)
    click.echo(f"✅ Configuration saved!")
    click.echo(f"   Token: {token[:8]}...")
    click.echo(f"   Server: {server}")


@config.command()
def show():
    """Show current configuration."""
    token = get_submission_token()
    server = get_submission_server()

    if token:
        click.echo(f"Token: {token[:8]}...")
    else:
        click.echo("Token: Not configured")

    click.echo(f"Server: {server}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--token",
    "-t",
    default=None,
    help="Access token for authentication (uses stored token if not provided)",
)
@click.option(
    "--server",
    "-s",
    default=None,
    help="Submission server URL (uses stored server if not provided)",
)
def submit(file, token, server):
    """Submit a file or directory to the submission platform. Directories are automatically zipped."""
    # Use stored token if not provided
    if token is None:
        token = get_submission_token()
        if token is None:
            click.echo(
                "❌ Error: No token provided and no token configured.",
                err=True,
            )
            click.echo(
                "   Run 'hwg-ml config init --token YOUR_TOKEN' to configure your token.",
                err=True,
            )
            sys.exit(1)

    # Use stored server if not provided
    if server is None:
        server = get_submission_server()
    try:
        result = submit_file(file, token, server)
        sys.exit(0)
    except FileNotFoundError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)
    except requests.HTTPError as e:
        click.echo(f"❌ HTTP Error: {e}", err=True)
        if e.response is not None:
            try:
                error_detail = e.response.json()
                click.echo(f"   Details: {error_detail}", err=True)
            except:
                click.echo(f"   Response: {e.response.text}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
