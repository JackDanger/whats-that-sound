"""Main CLI entry point for whats-that-sound."""

import click
from pathlib import Path
from rich.console import Console

from .models import ModelManager
from .organizer import MusicOrganizer

console = Console()


@click.group()
def cli():
    """Organize music collections using local LLMs."""
    pass


@cli.command()
@click.argument(
    "source_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.argument(
    "target_dir", type=click.Path(file_okay=False, dir_okay=True, path_type=Path)
)
@click.option("--model", "-m", required=True, help="Name of the LLM model to use")
@click.option(
    "--batch-size", "-b", default=1, help="Number of folders to process at once"
)
def organize(source_dir: Path, target_dir: Path, model: str, batch_size: int):
    """Organize music from SOURCE_DIR into TARGET_DIR using the specified model."""
    try:
        # Create target directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)

        # Initialize model manager
        model_manager = ModelManager()

        # Ensure model is downloaded
        console.print(f"[cyan]Checking for model: {model}[/cyan]")
        model_path = model_manager.ensure_model(model)

        # Initialize organizer
        organizer = MusicOrganizer(model_path, source_dir, target_dir)

        # Run organization process
        organizer.organize()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e))


@cli.command()
@click.option("--download", "-d", help="Download a specific model")
def models(download: str):
    """List downloaded models or download a new one."""
    model_manager = ModelManager()

    if download:
        console.print(f"[cyan]Downloading model: {download}[/cyan]")
        try:
            model_path = model_manager.download_model(download)
            console.print(f"[green]✓ Model downloaded to: {model_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error downloading model: {e}[/red]")
            raise click.ClickException(str(e))
    else:
        # List models
        models = model_manager.list_models()
        if models:
            console.print("[cyan]Downloaded models:[/cyan]")
            for model in models:
                console.print(f"  • {model}")
        else:
            console.print("[yellow]No models downloaded yet.[/yellow]")
            console.print("Use --download to download a model from Hugging Face.")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
