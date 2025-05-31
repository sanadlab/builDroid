"""Main script for the autogpt package."""
from pathlib import Path
from typing import Optional

import click

@click.group(invoke_without_command=True)
@click.option(
    "--ai-settings",
    "-C",
    help=(
        "Specifies which ai_settings.yaml file to use, relative to the Auto-GPT"
        " root directory. Will also automatically skip the re-prompt."
    ),
)
@click.option(
    "-l",
    "--continuous-limit",
    type=int,
    help="Defines the number of times to run in continuous mode",
)
@click.option("--debug", is_flag=True, help="Enable Debug Mode")
@click.option("--stream", is_flag=True, help="Chat Stream Mode")
@click.option(
    "--experiment-file",
    type=str,
    multiple=False,
    help="the path to the file containing the configuration of the agent for the experiment.",
)
@click.pass_context
def main(
    ctx: click.Context,
    continuous_limit: int,
    ai_settings: str,
    debug: bool,
    stream: bool,
    experiment_file: str
) -> None:
    """
    Welcome to AutoGPT an experimental open-source application showcasing the capabilities of the GPT-4 pushing the boundaries of AI.

    Start an Auto-GPT assistant.
    """
    # Put imports inside function to avoid importing everything when starting the CLI
    from autogpt.app.main import run_auto_gpt

    if ctx.invoked_subcommand is None:
        run_auto_gpt(
            continuous_limit=continuous_limit,
            ai_settings=ai_settings,
            debug=debug,
            stream=stream,
            working_directory=Path(
                __file__
            ).parent.parent.parent,  # TODO: make this an option
            experiment_file=experiment_file
        )


if __name__ == "__main__":
    main()
