"""
Tests for the CLI module.
"""
import pytest
import json
import yaml
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import CLI functions directly to avoid heavy dependencies
import sys
sys.path.insert(0, 'src')
from greenlightadv_shanaka.cli import (
    load_config,
    validate_config,
    create_sample_config,
    setup_logging
)


class TestConfigLoading:
    """Tests for configuration loading functionality."""
    
    def test_load_json_config(self):
        """Test loading JSON configuration file."""
        config_data = {
            "simulation": {"season_length": 5},
            "mqtt": {"enable": False}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            loaded_config = load_config(config_path)
            assert loaded_config == config_data
        finally:
            os.unlink(config_path)
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration file."""
        config_data = {
            "simulation": {"season_length": 5},
            "mqtt": {"enable": False}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            loaded_config = load_config(config_path)
            assert loaded_config == config_data
        finally:
            os.unlink(config_path)
    
    def test_load_nonexistent_config(self):
        """Test error handling for nonexistent config file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")
    
    def test_load_invalid_json(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid configuration file format"):
                load_config(config_path)
        finally:
            os.unlink(config_path)
    
    def test_load_unsupported_format(self):
        """Test error handling for unsupported file format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some content")
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported config file format"):
                load_config(config_path)
        finally:
            os.unlink(config_path)


class TestConfigValidation:
    """Tests for configuration validation."""
    
    def test_validate_minimal_config(self):
        """Test validation with minimal configuration."""
        config = {}
        validated = validate_config(config)
        
        # Should contain all default values
        assert "simulation" in validated
        assert "mqtt" in validated
        assert "model" in validated
        assert "greenhouse" in validated
        assert "output" in validated
        
        # Check specific defaults
        assert validated["simulation"]["season_length"] == 10
        assert validated["mqtt"]["enable"] is True
        assert validated["model"]["is_mature"] is True
    
    def test_validate_config_with_overrides(self):
        """Test validation with configuration overrides."""
        config = {
            "simulation": {"season_length": 5},
            "mqtt": {"enable": False, "broker_port": 8883}
        }
        
        validated = validate_config(config)
        
        # Should override specific values
        assert validated["simulation"]["season_length"] == 5
        assert validated["mqtt"]["enable"] is False
        assert validated["mqtt"]["broker_port"] == 8883
        
        # Should keep other defaults
        assert validated["simulation"]["first_day"] == 91
        assert validated["mqtt"]["broker_host"] == "localhost"
    
    def test_validate_invalid_season_length(self):
        """Test validation error for invalid season_length."""
        config = {"simulation": {"season_length": -1}}
        
        with pytest.raises(ValueError, match="season_length must be positive"):
            validate_config(config)
    
    def test_validate_invalid_season_interval(self):
        """Test validation error for invalid season_interval."""
        config = {"simulation": {"season_interval": 0}}
        
        with pytest.raises(ValueError, match="season_interval must be positive"):
            validate_config(config)
    
    def test_validate_invalid_first_day(self):
        """Test validation error for invalid first_day."""
        config = {"simulation": {"first_day": 400}}
        
        with pytest.raises(ValueError, match="first_day must be between 1 and 365"):
            validate_config(config)
    
    def test_validate_invalid_mqtt_port(self):
        """Test validation error for invalid MQTT port."""
        config = {"mqtt": {"broker_port": 70000}}
        
        with pytest.raises(ValueError, match="MQTT broker_port must be between 1 and 65535"):
            validate_config(config)
    
    def test_validate_nonexistent_epw_file(self):
        """Test warning for nonexistent EPW file."""
        config = {"simulation": {"epw_path": "/nonexistent/file.epw"}}
        
        with patch('greenlightadv_shanaka.cli.logging') as mock_logging:
            validated = validate_config(config)
            
            # Should not raise error but log warning
            mock_logging.warning.assert_called_once()
            assert "Weather file not found" in mock_logging.warning.call_args[0][0]
    
    def test_validate_no_epw_file(self):
        """Test validation works without EPW file (uses artificial weather)."""
        config = {"simulation": {"epw_path": None}}
        
        validated = validate_config(config)
        
        # Should work fine without weather file
        assert validated["simulation"]["epw_path"] is None


class TestSampleConfigCreation:
    """Tests for sample configuration creation."""
    
    def test_create_json_sample_config(self):
        """Test creating JSON sample configuration."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            create_sample_config(config_path)
            
            # Verify file was created and is valid JSON
            assert Path(config_path).exists()
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Verify structure
            assert "simulation" in config
            assert "mqtt" in config
            assert "model" in config
            assert "greenhouse" in config
            assert "output" in config
        finally:
            os.unlink(config_path)
    
    def test_create_yaml_sample_config(self):
        """Test creating YAML sample configuration."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        try:
            create_sample_config(config_path)
            
            # Verify file was created and is valid YAML
            assert Path(config_path).exists()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Verify structure
            assert "simulation" in config
            assert "mqtt" in config
            assert "model" in config
            assert "greenhouse" in config
            assert "output" in config
        finally:
            os.unlink(config_path)


class TestLoggingSetup:
    """Tests for logging setup."""
    
    def test_setup_logging_info(self):
        """Test setting up INFO level logging."""
        with patch('greenlightadv_shanaka.cli.logging.basicConfig') as mock_config:
            setup_logging("INFO")
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert kwargs['level'] == 20  # INFO level
    
    def test_setup_logging_debug(self):
        """Test setting up DEBUG level logging."""
        with patch('greenlightadv_shanaka.cli.logging.basicConfig') as mock_config:
            setup_logging("DEBUG")
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert kwargs['level'] == 10  # DEBUG level


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    @patch('greenlightadv_shanaka.cli.run_simulation')
    def test_main_with_config_file(self, mock_run):
        """Test main function with config file argument."""
        # Create temporary config file
        config_data = {"simulation": {"season_length": 1}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # Mock sys.argv
            with patch('sys.argv', ['cli.py', config_path]):
                from greenlightadv_shanaka.cli import main
                main()
            
            # Verify simulation was called
            mock_run.assert_called_once()
        finally:
            os.unlink(config_path)
    
    def test_main_with_create_config(self):
        """Test main function with create-config option."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            # Mock sys.argv
            with patch('sys.argv', ['cli.py', '--create-config', config_path]):
                from greenlightadv_shanaka.cli import main
                main()
            
            # Verify config file was created
            assert Path(config_path).exists()
        finally:
            os.unlink(config_path)