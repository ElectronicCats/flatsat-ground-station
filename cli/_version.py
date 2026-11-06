"""Version resolution for the legacy `cli` import path.

The real implementation is `modules.utils._version`; this only forwards to it so
the version can never drift between the two import paths.
"""

from modules.utils._version import __version__, get_version

__all__ = ["__version__", "get_version"]
