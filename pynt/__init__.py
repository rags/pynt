"""
Lightweight Python Build Tool
"""

__version__ = "0.8.3"
__license__ = "MIT License"
__contact__ = "http://rags.github.com/pynt/"
from ._pynt import task, main
import pkgutil

__path__ = pkgutil.extend_path(__path__,__name__)

__all__ = ["task",  "main"]
