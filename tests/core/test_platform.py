"""Test platform utilities."""

import pytest
import sys
from unittest.mock import patch, mock_open

from hits_core.platform.actions import (
    PlatformAction,
    is_wsl,
    detect_terminal_emulator,
    get_platform_info,
)


class TestWSLDetection:
    def test_is_wsl_false_on_windows(self):
        with patch.object(sys, 'platform', 'win32'):
            assert is_wsl() is False
    
    def test_is_wsl_false_on_macos(self):
        with patch.object(sys, 'platform', 'darwin'):
            assert is_wsl() is False
    
    def test_is_wsl_true_with_microsoft(self):
        with patch.object(sys, 'platform', 'linux'):
            with patch('builtins.open', mock_open(read_data='Linux version 5.10.16.3-microsoft-standard')):
                assert is_wsl() is True
    
    def test_is_wsl_false_regular_linux(self):
        with patch.object(sys, 'platform', 'linux'):
            with patch('builtins.open', mock_open(read_data='Linux version 5.15.0-generic')):
                assert is_wsl() is False


class TestPlatformAction:
    def test_open_url_success(self):
        with patch('hits_core.platform.actions.is_wsl', return_value=False):
            with patch('webbrowser.open', return_value=True) as mock_open:
                result = PlatformAction.open_url('https://example.com')
                assert result is True
                mock_open.assert_called_once_with('https://example.com')
    
    def test_open_url_exception(self):
        with patch('hits_core.platform.actions.is_wsl', return_value=False):
            with patch('webbrowser.open', side_effect=Exception("Browser error")):
                result = PlatformAction.open_url('https://example.com')
                assert result is False
    
    def test_execute_url(self):
        with patch.object(PlatformAction, 'open_url', return_value=True) as mock:
            result = PlatformAction.execute('url', 'https://example.com')
            assert result is True
            mock.assert_called_once_with('https://example.com')
    
    def test_execute_shell(self):
        with patch.object(PlatformAction, 'run_shell', return_value=True) as mock:
            result = PlatformAction.execute('shell', 'echo hello')
            assert result is True
            mock.assert_called_once_with('echo hello')
    
    def test_execute_app(self):
        with patch.object(PlatformAction, 'launch_app', return_value=True) as mock:
            result = PlatformAction.execute('app', '/path/to/app')
            assert result is True
            mock.assert_called_once_with('/path/to/app')
    
    def test_execute_unknown_type(self):
        result = PlatformAction.execute('unknown', 'something')
        assert result is False
    
    def test_execute_case_insensitive(self):
        with patch.object(PlatformAction, 'open_url', return_value=True) as mock:
            result = PlatformAction.execute('URL', 'https://example.com')
            assert result is True
            mock.assert_called_once_with('https://example.com')


class TestGetPlatformInfo:
    def test_returns_dict(self):
        info = get_platform_info()
        assert isinstance(info, dict)
        assert 'system' in info
        assert 'is_wsl' in info
        assert 'terminal' in info
        assert 'python' in info
