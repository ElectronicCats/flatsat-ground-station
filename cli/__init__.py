"""FlatSat Host CLI package.

Layered structure (mirrors the CatSniffer/catnip pattern):
  cli.app       -> root click group, global options and command registration
  cli.session   -> device discovery/selection and shell I/O (bridges to core/)
  cli.commands  -> one click command per module
  cli.ui        -> presentation helpers (banner, tables, console output)
"""

__version__ = "1.0.0"
