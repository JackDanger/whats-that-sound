"""Tests for the model manager module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.models import ModelManager


@pytest.fixture
def temp_model_dir(tmp_path):
    """Create a temporary model directory with HF cache structure."""
    model_dir = tmp_path / "huggingface" / "hub"
    model_dir.mkdir(parents=True)
    return model_dir


@pytest.fixture
def model_manager(temp_model_dir):
    """Create a ModelManager instance with temporary directory."""
    return ModelManager(model_dir=temp_model_dir)


class TestModelManager:
    """Test cases for ModelManager class."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates the model directory."""
        model_dir = tmp_path / "test_models"
        assert not model_dir.exists()

        ModelManager(model_dir=model_dir)
        assert model_dir.exists()

    def test_list_models_empty(self, model_manager):
        """Test listing models when directory is empty."""
        models = model_manager.list_models()
        assert models == []

    def test_list_models_with_files(self, model_manager, temp_model_dir):
        """Test listing models when GGUF files exist in HF cache structure."""
        # Create HF cache structure: models--{org}--{model}/snapshots/{commit_hash}/
        
        # Create first model: TheBloke/Llama-2-7B-GGUF
        model1_dir = temp_model_dir / "models--TheBloke--Llama-2-7B-GGUF"
        model1_snapshot = model1_dir / "snapshots" / "abc123"
        model1_snapshot.mkdir(parents=True)
        (model1_snapshot / "llama-2-7b.Q4_K_M.gguf").touch()
        
        # Create second model: microsoft/DialoGPT-small
        model2_dir = temp_model_dir / "models--microsoft--DialoGPT-small"
        model2_snapshot = model2_dir / "snapshots" / "def456"
        model2_snapshot.mkdir(parents=True)
        (model2_snapshot / "model.Q5_K_M.gguf").touch()
        
        # Create non-model directory (should be ignored)
        (temp_model_dir / "not_a_model").mkdir()
        
        models = model_manager.list_models()
        assert len(models) == 2
        assert "TheBloke/Llama-2-7B-GGUF/llama-2-7b.Q4_K_M.gguf" in models
        assert "microsoft/DialoGPT-small/model.Q5_K_M.gguf" in models

    @patch("src.models.hf_hub_download")
    @patch("src.models.HfFileSystem")
    def test_download_model_success(
        self, mock_hf_fs_class, mock_download, model_manager, temp_model_dir
    ):
        """Test successful model download using HF cache."""
        # Mock the file system
        mock_fs = Mock()
        mock_fs.ls.return_value = ["test_user/test-model/test-model.Q4_K_M.gguf"]
        mock_hf_fs_class.return_value = mock_fs

        # Mock the download to return a path in HF cache
        hf_cache_path = temp_model_dir / "models--test_user--test-model" / "snapshots" / "abc123" / "test-model.Q4_K_M.gguf"
        mock_download.return_value = str(hf_cache_path)

        result = model_manager.download_model("test_user/test-model")

        assert result == Path(mock_download.return_value)
        mock_fs.ls.assert_called_once_with("test_user/test-model", detail=False)
        mock_download.assert_called_once()
        # Verify it's called without local_dir (uses HF cache)
        call_args = mock_download.call_args
        assert "local_dir" not in call_args.kwargs

    @patch("src.models.HfFileSystem")
    def test_download_model_no_gguf_files(self, mock_hf_fs_class, model_manager):
        """Test download when no GGUF files are found."""
        mock_fs = Mock()
        mock_fs.ls.return_value = []
        mock_hf_fs_class.return_value = mock_fs

        with pytest.raises(ValueError, match="No GGUF files found"):
            model_manager.download_model("test_user/test-model")

    def test_ensure_model_local_exists(self, model_manager, temp_model_dir):
        """Test ensure_model with existing local model in HF cache."""
        # Create a model in HF cache structure
        model_dir = temp_model_dir / "models--TheBloke--TestModel-GGUF"
        model_snapshot = model_dir / "snapshots" / "abc123"
        model_snapshot.mkdir(parents=True)
        model_file = model_snapshot / "test-model.gguf"
        model_file.touch()

        result = model_manager.ensure_model("TheBloke/TestModel-GGUF/test-model.gguf")
        assert result == model_file

    def test_ensure_model_absolute_path(self, tmp_path):
        """Test ensure_model with absolute path."""
        model_file = tmp_path / "absolute-model.gguf"
        model_file.touch()

        manager = ModelManager()
        result = manager.ensure_model(str(model_file))
        assert result == model_file

    @patch("src.models.ModelManager.download_model")
    def test_ensure_model_download_required(self, mock_download, model_manager):
        """Test ensure_model when download is required."""
        mock_download.return_value = Path("/path/to/model.gguf")

        result = model_manager.ensure_model("TheBloke/Model-GGUF")

        mock_download.assert_called_once_with("TheBloke/Model-GGUF")
        assert result == Path("/path/to/model.gguf")

    def test_get_model_info(self, temp_model_dir):
        """Test getting model information."""
        model_file = temp_model_dir / "test-model.gguf"
        model_file.write_bytes(b"x" * 1024 * 1024)  # 1 MB

        manager = ModelManager()
        info = manager.get_model_info(model_file)

        assert info["path"] == str(model_file)
        assert info["name"] == "test-model.gguf"
        assert info["size_mb"] == 1.0

    def test_get_model_info_not_found(self, model_manager):
        """Test getting info for non-existent model."""
        with pytest.raises(FileNotFoundError):
            model_manager.get_model_info(Path("/non/existent/model.gguf"))

    @patch("src.models.HfApi")
    def test_search_models_success(self, mock_hf_api_class, model_manager):
        """Test successful model search."""
        mock_api = Mock()
        mock_model = Mock()
        mock_model.id = "test/model"
        mock_model.downloads = 1000
        mock_model.description = "Test model"
        mock_model.tags = ["gguf", "llama"]
        mock_model.created_at = "2023-01-01"
        mock_model.last_modified = "2023-01-02"
        
        mock_api.list_models.return_value = [mock_model]
        mock_hf_api_class.return_value = mock_api

        results = model_manager.search_models("test query")
        
        assert len(results) == 1
        assert results[0]["id"] == "test/model"
        assert results[0]["downloads"] == 1000
        mock_api.list_models.assert_called_once_with(
            search="test query",
            library="gguf",
            limit=20,
            sort="downloads",
            direction=-1
        )
