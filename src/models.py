"""Model management for downloading and loading LLMs."""
import os
from pathlib import Path
from typing import List, Optional
from huggingface_hub import hf_hub_download, HfFileSystem
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn
from rich.console import Console

console = Console()


class ModelManager:
    """Manages downloading and listing of GGUF models."""
    
    def __init__(self, model_dir: Optional[Path] = None):
        """Initialize the model manager.
        
        Args:
            model_dir: Directory to store models. Defaults to ~/.cache/whats-that-sound/models
        """
        if model_dir is None:
            self.model_dir = Path.home() / ".cache" / "whats-that-sound" / "models"
        else:
            self.model_dir = Path(model_dir)
        
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def list_models(self) -> List[str]:
        """List all downloaded GGUF models."""
        models = []
        if self.model_dir.exists():
            for file in self.model_dir.glob("**/*.gguf"):
                # Get relative path from model_dir
                relative_path = file.relative_to(self.model_dir)
                models.append(str(relative_path))
        return sorted(models)
    
    def download_model(self, model_id: str, filename: Optional[str] = None) -> Path:
        """Download a GGUF model from Hugging Face.
        
        Args:
            model_id: HuggingFace model ID (e.g., "TheBloke/Llama-2-7B-GGUF")
            filename: Specific GGUF file to download. If None, downloads the first GGUF found.
        
        Returns:
            Path to the downloaded model file
        """
        # Create subdirectory for this model
        model_subdir = self.model_dir / model_id.replace("/", "_")
        model_subdir.mkdir(parents=True, exist_ok=True)
        
        try:
            if filename is None:
                # Find the first GGUF file in the repository
                console.print(f"[cyan]Searching for GGUF files in {model_id}...[/cyan]")
                
                # Use HfFileSystem to list files
                fs = HfFileSystem()
                files = fs.ls(f"{model_id}", detail=False)
                gguf_files = [f.split('/')[-1] for f in files if f.endswith('.gguf')]
                
                if not gguf_files:
                    raise ValueError(f"No GGUF files found in {model_id}")
                
                # Choose a reasonable default (prefer Q4_K_M or Q5_K_M quantizations)
                filename = gguf_files[0]
                for f in gguf_files:
                    if 'q4_k_m' in f.lower() or 'q5_k_m' in f.lower():
                        filename = f
                        break
                
                console.print(f"[green]Found GGUF file: {filename}[/green]")
            
            # Check if already downloaded
            local_path = model_subdir / filename
            if local_path.exists():
                console.print(f"[yellow]Model already downloaded: {local_path}[/yellow]")
                return local_path
            
            # Download with progress bar
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
                        progress.update(download_task, completed=progress_info["downloaded"])
                
                downloaded_path = hf_hub_download(
                    repo_id=model_id,
                    filename=filename,
                    local_dir=model_subdir,
                    local_dir_use_symlinks=False,
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
            return self.model_dir / model_spec
        
        # Check if it's a path to a local file
        if Path(model_spec).exists() and model_spec.endswith('.gguf'):
            return Path(model_spec)
        
        # Check partial match (just the filename)
        for model in local_models:
            if Path(model).name == model_spec or model_spec in str(model):
                return self.model_dir / model
        
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
            
            raise ValueError(f"Model '{model_spec}' not found locally or on HuggingFace")
    
    def get_model_info(self, model_path: Path) -> dict:
        """Get information about a model file."""
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        
        return {
            "path": str(model_path),
            "name": model_path.name,
            "size_mb": model_path.stat().st_size / (1024 * 1024),
        } 