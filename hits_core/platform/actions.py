"""Cross-platform utilities without GUI dependencies."""

import os
import subprocess
import sys
import webbrowser
from typing import Optional, Tuple


def is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    if sys.platform != "linux":
        return False
    
    try:
        with open("/proc/version", "r") as f:
            version = f.read().lower()
            return "microsoft" in version or "wsl" in version
    except Exception:
        return False


def detect_terminal_emulator() -> Optional[str]:
    """Detect available terminal emulator on Linux."""
    terminals = [
        ("wt", "wt.exe"),  # Windows Terminal via WSL
        ("gnome-terminal", "gnome-terminal"),
        ("konsole", "konsole"),
        ("xfce4-terminal", "xfce4-terminal"),
        ("xterm", "xterm"),
        ("alacritty", "alacritty"),
        ("kitty", "kitty"),
        ("terminator", "terminator"),
        ("urxvt", "urxvt"),
    ]
    
    for name, cmd in terminals:
        if cmd == "wt.exe" and is_wsl():
            try:
                subprocess.run(["which", "wt.exe"], capture_output=True, check=True)
                return "wt"
            except Exception:
                continue
        
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return name
        except Exception:
            continue
    
    return None


def get_wsl_windows_path(linux_path: str) -> str:
    """Convert Linux path to Windows path for WSL."""
    if not is_wsl():
        return linux_path
    
    try:
        result = subprocess.run(
            ["wslpath", "-w", linux_path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return linux_path


class PlatformAction:
    _is_wsl = is_wsl()
    _terminal_cache: Optional[str] = None
    
    @classmethod
    def _get_terminal(cls) -> Optional[str]:
        if cls._terminal_cache is None:
            cls._terminal_cache = detect_terminal_emulator()
        return cls._terminal_cache
    
    @staticmethod
    def open_url(url: str) -> bool:
        """Open URL in default browser - works on all platforms."""
        try:
            if is_wsl():
                try:
                    win_url = get_wsl_windows_path(url) if url.startswith("/") else url
                    subprocess.run(["cmd.exe", "/c", "start", win_url], check=True)
                    return True
                except Exception:
                    pass
            
            webbrowser.open(url)
            return True
        except Exception:
            return False
    
    @classmethod
    def run_shell(cls, command: str, terminal: bool = True) -> bool:
        """Execute shell command, optionally in a new terminal."""
        try:
            if not terminal:
                subprocess.Popen(command, shell=True)
                return True
            
            if sys.platform == "win32":
                return cls._run_shell_windows(command)
            elif sys.platform == "darwin":
                return cls._run_shell_macos(command)
            else:
                return cls._run_shell_linux(command)
        except Exception:
            return False
    
    @classmethod
    def _run_shell_windows(cls, command: str) -> bool:
        """Run shell command on Windows."""
        term = os.environ.get("TERM_PROGRAM", "")
        
        if term == "vscode" or "WT_SESSION" in os.environ:
            subprocess.Popen(["wt", "cmd", "/k", command])
        else:
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", command])
        return True
    
    @classmethod
    def _run_shell_macos(cls, command: str) -> bool:
        """Run shell command on macOS."""
        script = f'tell application "Terminal" to do script "{command}"'
        subprocess.Popen(["osascript", "-e", script])
        return True
    
    @classmethod
    def _run_shell_linux(cls, command: str) -> bool:
        """Run shell command on Linux (including WSL)."""
        if cls._is_wsl:
            try:
                subprocess.run(["which", "wt.exe"], capture_output=True, check=True)
                subprocess.Popen([
                    "wt.exe", "-d", ".",
                    "bash", "-c", f"{command}; echo; read -p 'Press Enter to close...'"
                ])
                return True
            except Exception:
                pass
        
        terminal = cls._get_terminal()
        
        if terminal == "gnome-terminal":
            subprocess.Popen([
                "gnome-terminal", "--", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        elif terminal == "konsole":
            subprocess.Popen([
                "konsole", "-e", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        elif terminal == "xfce4-terminal":
            subprocess.Popen([
                "xfce4-terminal", "-e", f"bash -c '{command}; echo; read -p \"Press Enter to close...\"'"
            ])
        elif terminal == "alacritty":
            subprocess.Popen([
                "alacritty", "-e", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        elif terminal == "kitty":
            subprocess.Popen([
                "kitty", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        elif terminal in ("xterm", "urxvt"):
            subprocess.Popen([
                terminal, "-e", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        else:
            subprocess.Popen([
                "x-terminal-emulator", "-e", "bash", "-c",
                f"{command}; echo; read -p 'Press Enter to close...'"
            ])
        
        return True
    
    @classmethod
    def launch_app(cls, app_path: str) -> bool:
        """Launch an application."""
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", app_path], shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", app_path])
            elif cls._is_wsl:
                win_path = get_wsl_windows_path(app_path)
                subprocess.Popen(["cmd.exe", "/c", "start", "", win_path])
            else:
                subprocess.Popen([app_path])
            return True
        except Exception:
            return False
    
    @staticmethod
    def execute(action_type: str, action: str) -> bool:
        """Execute action based on type."""
        action_type = action_type.lower().strip()
        
        if action_type == "url":
            return PlatformAction.open_url(action)
        elif action_type == "shell":
            return PlatformAction.run_shell(action)
        elif action_type == "app":
            return PlatformAction.launch_app(action)
        else:
            return False


def get_platform_info() -> dict:
    """Get current platform information."""
    return {
        "system": sys.platform,
        "is_wsl": is_wsl(),
        "terminal": detect_terminal_emulator(),
        "python": sys.version,
    }
