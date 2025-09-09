"""Main CLI entry point for whats-that-sound.

Boot the FastAPI server for the React UI with sensible defaults:
- Source/target directories can be provided via flags or env (WTS_SOURCE_DIR/WTS_TARGET_DIR)
- Inference can be provided via --model or --inference-url, env (WTS_MODEL/WTS_INFERENCE_URL),
  or defaults to a local llama-compatible server at http://localhost:11434/v1
"""

import click
from pathlib import Path
from rich.console import Console
import os
import webbrowser
import subprocess
import signal
import sys
import shutil

from .organizer import MusicOrganizer
from .inference import InferenceProvider
from .server import create_app
import uvicorn

console = Console()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--source-dir",
    required=False,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Source directory containing unorganized music (env: WTS_SOURCE_DIR)",
)
@click.option(
    "--target-dir",
    required=False,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Target directory where organized music will be written (env: WTS_TARGET_DIR)",
)
@click.option("--model", "-m", help="Model name (env: WTS_MODEL), e.g. 'gpt-5' or 'gemini-2.5-pro'")
@click.option("--inference-url", help="HTTP base URL for llama-compatible server (env: WTS_INFERENCE_URL), e.g. http://localhost:11434/v1")
@click.option("--host", default=os.getenv("HOST", "0.0.0.0"), show_default=True, help="Server host")
@click.option("--port", default=int(os.getenv("PORT", "8000")), show_default=True, help="Server port", type=int)
@click.option("--open-browser/--no-open-browser", default=True, show_default=True, help="Open browser at startup")
@click.option("--reload/--no-reload", default=False, show_default=True, help="Auto-reload backend (dev)")
@click.option("--vite-dev/--no-vite-dev", default=None, help="Run Vite dev server for HMR (defaults to match --reload)")
def main_cli(
    source_dir: Path | None,
    target_dir: Path | None,
    model: str | None,
    inference_url: str | None,
    host: str,
    port: int,
    open_browser: bool,
    reload: bool,
    vite_dev: bool | None,
):
    """Serve the web UI with a FastAPI backend.

    You may specify --model OR --inference-url. If neither is provided, env vars are used,
    otherwise defaults to a local llama-compatible API at http://localhost:11434/v1.
    """
    try:
        project_root = Path(__file__).resolve().parent.parent

        # Resolve directories with env/defaults
        env_source = os.getenv("WTS_SOURCE_DIR")
        env_target = os.getenv("WTS_TARGET_DIR")

        if source_dir is None:
            if env_source:
                source_dir = Path(env_source)
            elif (project_root / "tmp-src").exists():
                source_dir = project_root / "tmp-src"
            else:
                source_dir = Path.home() / "Music" / "Unsorted"

        if target_dir is None:
            if env_target:
                target_dir = Path(env_target)
            elif (project_root / "tmp-dst").exists():
                target_dir = project_root / "tmp-dst"
            else:
                target_dir = Path.home() / "Music" / "Organized"

        # Create target directory if it doesn't exist
        target_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        # Configure inference preference: flag -> env -> default
        env_model = os.getenv("WTS_MODEL")
        env_infer = os.getenv("WTS_INFERENCE_URL")

        # If both flags provided, it's invalid
        if model and inference_url:
            raise click.ClickException("Provide at most one of --model or --inference-url")

        if not model and not inference_url:
            # Fall back to env
            model = env_model if env_model else None
            inference_url = env_infer if env_infer else None

        if not model and not inference_url:
            # Final default: local llama-compatible server
            inference_url = "http://localhost:11434/v1"

        # Configure inference
        if inference_url:
            # Use llama HTTP server
            # Propagate to worker/child processes
            os.environ["LLAMA_API_BASE"] = inference_url
            provider = InferenceProvider(provider="llama", model="", llama_base_url=inference_url)
        else:
            # Map model to provider heuristically
            normalized = model.lower()
            if normalized.startswith("gpt") or normalized.startswith("o"):
                # OpenAI family
                token = os.getenv("OPENAI_API_TOKEN") or os.getenv("OPENAI_API_KEY")
                if not token:
                    raise click.ClickException("OPENAI_API_TOKEN is required for OpenAI models")
                provider = InferenceProvider(provider="openai", model=model, openai_api_key=token)
            elif normalized.startswith("gemini"):
                token = os.getenv("GEMINI_API_TOKEN") or os.getenv("GOOGLE_API_KEY")
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

        # Start web server for UI
        url = f"http://{host}:{port}"
        console.print(f"[green]Starting What's That Sound on {url}[/green]")
        # If no built frontend found, hint about dev server
        dist_dir = project_root / "frontend" / "dist"
        if not dist_dir.exists():
            console.print("[dim]Tip: run 'npm run dev' in ./frontend for the React dev server (port 5173)[/dim]")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        # In dev, default vite_dev to match reload
        if vite_dev is None:
            vite_dev = reload

        if reload or vite_dev:
            # Orchestrate child processes: uvicorn (reload) and optional vite dev
            env = os.environ.copy()
            env["WTS_SOURCE_DIR"] = str(source_dir)
            env["WTS_TARGET_DIR"] = str(target_dir)
            env["WTS_DEV"] = "1"
            if inference_url:
                env["WTS_INFERENCE_URL"] = inference_url
                env["LLAMA_API_BASE"] = inference_url
                env.pop("WTS_MODEL", None)
            elif model:
                env["WTS_MODEL"] = model
                env.pop("WTS_INFERENCE_URL", None)

            processes: list[subprocess.Popen] = []
            try:
                # Start uvicorn in reload mode using import string + factory
                uvicorn_cmd = [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "src.cli:app_factory",
                    "--host",
                    host,
                    "--port",
                    str(port),
                    "--reload",
                    "--factory",
                ]
                processes.append(subprocess.Popen(uvicorn_cmd, env=env))

                # Optionally start Vite dev server
                if vite_dev:
                    npm = shutil.which("npm")
                    if not npm:
                        console.print("[yellow]npm not found on PATH; skipping Vite dev server. Install Node or run it manually.[/yellow]")
                    else:
                        frontend_dir = project_root / "frontend"
                        vite_cmd = [npm, "run", "dev"]
                        processes.append(subprocess.Popen(vite_cmd, cwd=str(frontend_dir), env=env))

                # Open browser once
                if open_browser:
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass

                # Handle signals and wait
                def handle_signal(signum, frame):
                    for p in processes:
                        try:
                            p.terminate()
                        except Exception:
                            pass
                signal.signal(signal.SIGINT, handle_signal)
                signal.signal(signal.SIGTERM, handle_signal)

                # Wait for uvicorn to exit; if it exits, shut down vite as well
                exit_code = processes[0].wait()
                for p in processes[1:]:
                    try:
                        p.terminate()
                        p.wait(timeout=5)
                    except Exception:
                        try:
                            p.kill()
                        except Exception:
                            pass
                sys.exit(exit_code)
            finally:
                for p in processes:
                    if p.poll() is None:
                        try:
                            p.kill()
                        except Exception:
                            pass
        else:
            app = create_app(organizer)
            uvicorn.run(app, host=host, port=port, reload=False)

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

# --- Factory for uvicorn --reload ---
def app_factory():
    """Build FastAPI app from environment settings. Used by uvicorn with --reload."""
    project_root = Path(__file__).resolve().parent.parent
    # Resolve dirs
    source_dir = os.getenv("WTS_SOURCE_DIR")
    target_dir = os.getenv("WTS_TARGET_DIR")
    if not source_dir:
        if (project_root / "tmp-src").exists():
            source_dir = str(project_root / "tmp-src")
        else:
            source_dir = str(Path.home() / "Music" / "Unsorted")
    if not target_dir:
        if (project_root / "tmp-dst").exists():
            target_dir = str(project_root / "tmp-dst")
        else:
            target_dir = str(Path.home() / "Music" / "Organized")

    # Inference from env
    model = os.getenv("WTS_MODEL")
    inference_url = os.getenv("WTS_INFERENCE_URL") or os.getenv("LLAMA_API_BASE")

    # Create provider
    if inference_url:
        os.environ["LLAMA_API_BASE"] = inference_url
        provider = InferenceProvider(provider="llama", model="", llama_base_url=inference_url)
    elif model:
        normalized = model.lower()
        if normalized.startswith("gpt") or normalized.startswith("o"):
            token = os.getenv("OPENAI_API_TOKEN") or os.getenv("OPENAI_API_KEY")
            if not token:
                raise RuntimeError("OPENAI_API_TOKEN is required for OpenAI models")
            provider = InferenceProvider(provider="openai", model=model, openai_api_key=token)
        elif normalized.startswith("gemini"):
            token = os.getenv("GEMINI_API_TOKEN") or os.getenv("GOOGLE_API_KEY")
            if not token:
                raise RuntimeError("GEMINI_API_TOKEN is required for Gemini models")
            provider = InferenceProvider(provider="gemini", model=model, gemini_api_key=token)
        else:
            provider = InferenceProvider(provider="llama", model=normalized)
    else:
        # Default local llama server
        inference_url = "http://localhost:11434/v1"
        os.environ["LLAMA_API_BASE"] = inference_url
        provider = InferenceProvider(provider="llama", model="", llama_base_url=inference_url)

    # Build organizer
    src_path = Path(source_dir)
    dst_path = Path(target_dir)
    dst_path.mkdir(parents=True, exist_ok=True)
    src_path.mkdir(parents=True, exist_ok=True)

    organizer = MusicOrganizer(Path("model"), src_path, dst_path)
    organizer.inference = provider
    organizer.structure_classifier.inference = provider
    organizer.proposal_generator.inference = provider

    return create_app(organizer)
