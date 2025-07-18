"""Model management for downloading and loading LLMs."""

import os
from pathlib import Path
from typing import List, Optional, Dict
from huggingface_hub import hf_hub_download, HfFileSystem, HfApi
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
)
from rich.console import Console

console = Console()


class ModelManager:
    """Manages downloading and listing of GGUF models."""

    def __init__(self, model_dir: Optional[Path] = None):
        """Initialize the model manager.

        Args:
            model_dir: Custom directory to store models. Defaults to standard HF cache ~/.cache/huggingface/hub
        """
        if model_dir is None:
            # Use standard HF cache directory
            self.model_dir = Path.home() / ".cache" / "huggingface" / "hub"
        else:
            self.model_dir = Path(model_dir)

        self.model_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> List[str]:
        """List all downloaded GGUF models in the HF cache."""
        models = []
        if self.model_dir.exists():
            # Scan HF cache structure: models--{org}--{model}/snapshots/{commit_hash}/
            for model_dir in self.model_dir.glob("models--*"):
                # Look in snapshots directory for the latest/main snapshot
                snapshots_dir = model_dir / "snapshots"
                if snapshots_dir.exists():
                    # Get the most recent snapshot (or main if it exists)
                    snapshot_dirs = list(snapshots_dir.iterdir())
                    if snapshot_dirs:
                        # Use the first snapshot found (HF manages versions)
                        for snapshot_dir in snapshot_dirs:
                            if snapshot_dir.is_dir():
                                # Find GGUF files in this snapshot
                                for gguf_file in snapshot_dir.glob("*.gguf"):
                                    # Convert model dir name back to repo format
                                    model_name = model_dir.name.replace("models--", "").replace("--", "/")
                                    models.append(f"{model_name}/{gguf_file.name}")
                                break
        return sorted(models)

    def search_models(self, search_query: str, limit: int = 20) -> List[Dict]:
        """Search for GGUF models on Hugging Face.

        Args:
            search_query: Search term to look for in model names
            limit: Maximum number of results to return

        Returns:
            List of model information dictionaries
        """
        api = HfApi()
        
        try:
            # Search for models with GGUF library and containing the search query
            models = api.list_models(
                search=search_query,
                library="gguf",
                limit=limit,
                sort="downloads",
                direction=-1
            )
            
            results = []
            for model in models:
                # Extract useful information
                model_info = {
                    "id": model.id,
                    "downloads": getattr(model, 'downloads', 0),
                    "description": getattr(model, 'description', None),
                    "tags": getattr(model, 'tags', []),
                    "created_at": getattr(model, 'created_at', None),
                    "updated_at": getattr(model, 'last_modified', None)
                }
                results.append(model_info)
            
            return results
            
        except Exception as e:
            console.print(f"[red]Error searching models: {e}[/red]")
            raise

    def download_model(self, model_id: str, filename: Optional[str] = None) -> Path:
        """Download a GGUF model from Hugging Face to the standard HF cache.

        Args:
            model_id: HuggingFace model ID (e.g., "TheBloke/Llama-2-7B-GGUF")
            filename: Specific GGUF file to download. If None, downloads the first GGUF found.

        Returns:
            Path to the downloaded model file in the HF cache
        """
        try:
            if filename is None:
                # Find the first GGUF file in the repository
                console.print(f"[cyan]Searching for GGUF files in {model_id}...[/cyan]")

                # Use HfFileSystem to list files
                fs = HfFileSystem()
                files = fs.ls(f"{model_id}", detail=False)
                gguf_files = [f.split("/")[-1] for f in files if f.endswith(".gguf")]

                if not gguf_files:
                    raise ValueError(f"No GGUF files found in {model_id}")

                # Choose a reasonable default (prefer Q4_K_M or Q5_K_M quantizations)
                filename = gguf_files[0]
                for f in gguf_files:
                    if "q4_k_m" in f.lower() or "q5_k_m" in f.lower():
                        filename = f
                        break

                console.print(f"[green]Found GGUF file: {filename}[/green]")

            # Download with progress bar - let HF handle the caching
            console.print(f"[cyan]Downloading {filename} from {model_id}...[/cyan]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console,
            ) as progress:
                download_task = progress.add_task(f"Downloading {filename}", total=None)

                def progress_callback(progress_info):
                    if progress_info.get("total"):
                        progress.update(download_task, total=progress_info["total"])
                    if progress_info.get("downloaded"):
                        progress.update(
                            download_task, completed=progress_info["downloaded"]
                        )

                # Use standard HF cache - no custom local_dir
                downloaded_path = hf_hub_download(
                    repo_id=model_id,
                    filename=filename,
                    resume_download=True,
                )

            console.print(f"[green]✓ Model downloaded successfully![/green]")
            return Path(downloaded_path)

        except Exception as e:
            console.print(f"[red]Error downloading model: {e}[/red]")
            raise

    def ensure_model(self, model_spec: str) -> Path:
        """Ensure a model is available, downloading if necessary.

        Args:
            model_spec: Either a local model name or a HuggingFace model ID

        Returns:
            Path to the model file
        """
        # Check if it's already downloaded
        local_models = self.list_models()

        # Check exact match
        if model_spec in local_models:
            # Find the actual file path in HF cache
            for model in local_models:
                if model == model_spec:
                    # Extract model_id and filename from the model spec
                    parts = model.split("/")
                    if len(parts) >= 2:
                        model_id = "/".join(parts[:-1])
                        filename = parts[-1]
                        # Find the file in HF cache
                        cache_dir = self.model_dir / f"models--{model_id.replace('/', '--')}"
                        for snapshot_dir in (cache_dir / "snapshots").iterdir():
                            if snapshot_dir.is_dir():
                                file_path = snapshot_dir / filename
                                if file_path.exists():
                                    return file_path
                    break

        # Check if it's a path to a local file
        if Path(model_spec).exists() and model_spec.endswith(".gguf"):
            return Path(model_spec)

        # Check partial match (just the filename)
        for model in local_models:
            if Path(model).name == model_spec or model_spec in str(model):
                # Find the actual file path in HF cache
                parts = model.split("/")
                if len(parts) >= 2:
                    model_id = "/".join(parts[:-1])
                    filename = parts[-1]
                    # Find the file in HF cache
                    cache_dir = self.model_dir / f"models--{model_id.replace('/', '--')}"
                    for snapshot_dir in (cache_dir / "snapshots").iterdir():
                        if snapshot_dir.is_dir():
                            file_path = snapshot_dir / filename
                            if file_path.exists():
                                return file_path

        # If not found locally, try to download from HuggingFace
        if "/" in model_spec:
            # It's a HuggingFace model ID
            return self.download_model(model_spec)
        else:
            # Try common model providers
            common_prefixes = ["TheBloke/", ""]
            for prefix in common_prefixes:
                try:
                    hf_id = f"{prefix}{model_spec}"
                    return self.download_model(hf_id)
                except Exception:
                    continue

            raise ValueError(
                f"Model '{model_spec}' not found locally or on HuggingFace"
            )

    def get_model_info(self, model_path: Path) -> dict:
        """Get information about a model file."""
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        return {
            "path": str(model_path),
            "name": model_path.name,
            "size_mb": model_path.stat().st_size / (1024 * 1024),
        }
