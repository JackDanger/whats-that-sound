"""Tests for the model manager module."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.models import ModelManager


@pytest.fixture
def temp_model_dir(tmp_path):
    """Create a temporary model directory."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
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
        """Test listing models when GGUF files exist."""
        # Create some test GGUF files
        (temp_model_dir / "model1.gguf").touch()
        (temp_model_dir / "subdir").mkdir()
        (temp_model_dir / "subdir" / "model2.gguf").touch()
        (temp_model_dir / "not_a_model.txt").touch()
        
        models = model_manager.list_models()
        assert len(models) == 2
        assert "model1.gguf" in models
        assert "subdir/model2.gguf" in models
    
    @patch('src.models.hf_hub_download')
    @patch('src.models.HfFileSystem')
    def test_download_model_success(self, mock_hf_fs_class, mock_download, model_manager, temp_model_dir):
        """Test successful model download."""
        # Mock the file system
        mock_fs = Mock()
        mock_fs.ls.return_value = ["test_user/test-model/test-model.Q4_K_M.gguf"]
        mock_hf_fs_class.return_value = mock_fs
        
        # Mock the download
        expected_path = temp_model_dir / "test_user_test-model" / "test-model.Q4_K_M.gguf"
        mock_download.return_value = str(expected_path)
        
        # Ensure parent directory exists but not the file
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        # Don't create the file - let the mock download do it
        
        result = model_manager.download_model("test_user/test-model")
        
        assert result == Path(mock_download.return_value)
        mock_fs.ls.assert_called_once_with("test_user/test-model", detail=False)
        mock_download.assert_called_once()
    
    @patch('src.models.HfFileSystem')
    def test_download_model_no_gguf_files(self, mock_hf_fs_class, model_manager):
        """Test download when no GGUF files are found."""
        mock_fs = Mock()
        mock_fs.ls.return_value = []
        mock_hf_fs_class.return_value = mock_fs
        
        with pytest.raises(ValueError, match="No GGUF files found"):
            model_manager.download_model("test_user/test-model")
    
    def test_download_model_already_exists(self, model_manager, temp_model_dir):
        """Test download when model already exists."""
        # Create existing model file
        model_subdir = temp_model_dir / "test_user_test-model"
        model_subdir.mkdir()
        model_file = model_subdir / "test-model.gguf"
        model_file.touch()
        
        with patch('src.models.HfFileSystem') as mock_hf_fs_class:
            mock_fs = Mock()
            mock_fs.ls.return_value = ["test_user/test-model/test-model.gguf"]
            mock_hf_fs_class.return_value = mock_fs
            
            result = model_manager.download_model("test_user/test-model", "test-model.gguf")
            assert result == model_file
    
    def test_ensure_model_local_exists(self, model_manager, temp_model_dir):
        """Test ensure_model with existing local model."""
        # Create a local model
        model_file = temp_model_dir / "local-model.gguf"
        model_file.touch()
        
        result = model_manager.ensure_model("local-model.gguf")
        assert result == model_file
    
    def test_ensure_model_absolute_path(self, tmp_path):
        """Test ensure_model with absolute path."""
        model_file = tmp_path / "absolute-model.gguf"
        model_file.touch()
        
        manager = ModelManager()
        result = manager.ensure_model(str(model_file))
        assert result == model_file
    
    @patch('src.models.ModelManager.download_model')
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