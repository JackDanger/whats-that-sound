"""Main CLI entry point for whats-that-sound."""

import click
from pathlib import Path
from rich.console import Console

from .organizer import MusicOrganizer
from .inference import InferenceProvider

console = Console()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--source-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the source directory containing unorganized music",
)
@click.option(
    "--target-dir",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the target directory where organized music will be written",
)
@click.option("--model", "-m", help="Model name, e.g. 'gpt-5' or 'gemini-2.5-pro'")
@click.option("--inference-url", help="HTTP base URL for a llama-server, e.g. http://localhost:11434/v1")
def main_cli(source_dir: Path, target_dir: Path, model: str | None, inference_url: str | None):
    """Organize music from SOURCE_DIR into TARGET_DIR using an inference provider.

    Exactly one of --model or --inference-url must be provided.
    """
    try:
        # Validate args
        if bool(model) == bool(inference_url):
            raise click.ClickException("Provide exactly one of --model or --inference-url")

        # Create target directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)

        # Configure inference
        if inference_url:
            # Use llama HTTP server
            import os as _os
            # Propagate to worker/child processes
            _os.environ["LLAMA_API_BASE"] = inference_url
            provider = InferenceProvider(provider="llama", model="", llama_base_url=inference_url)
        else:
            # Map model to provider heuristically
            normalized = model.lower()
            if normalized.startswith("gpt") or normalized.startswith("o"):
                # OpenAI family
                import os as _os
                token = _os.getenv("OPENAI_API_TOKEN") or _os.getenv("OPENAI_API_KEY")
                if not token:
                    raise click.ClickException("OPENAI_API_TOKEN is required for OpenAI models")
                provider = InferenceProvider(provider="openai", model=model, openai_api_key=token)
            elif normalized.startswith("gemini"):
                import os as _os
                token = _os.getenv("GEMINI_API_TOKEN") or _os.getenv("GOOGLE_API_KEY")
                if not token:
                    raise click.ClickException("GEMINI_API_TOKEN is required for Gemini models")
                provider = InferenceProvider(provider="gemini", model=model, gemini_api_key=token)
            else:
                # Default to llama for unknowns
                provider = InferenceProvider(provider="llama", model=normalized)

        # Initialize organizer
        organizer = MusicOrganizer(Path(model or "model"), source_dir, target_dir)
        # Inject our provider on the organizer (already used inside components)
        organizer.inference = provider
        organizer.structure_classifier.inference = provider
        organizer.proposal_generator.inference = provider

        # Run organization process
        organizer.organize()

    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e))

def main():
    """Main entry point."""
    main_cli()

if __name__ == "__main__":
    main()
