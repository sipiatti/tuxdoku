"""Tuxdoku - a cheerful penguin logic puzzle (Queens / Star Battle style)."""
import os as _os
import warnings as _warnings

_os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Ubuntu's python3-pygame prints a harmless AVX2 performance warning on import.
_warnings.filterwarnings("ignore", message=r"Your system is avx2 capable", category=RuntimeWarning)

__version__ = "0.2.0"
