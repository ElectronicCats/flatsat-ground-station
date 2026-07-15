"""FlatSat Host CLI package.

Layered structure (mirrors the CatSniffer/catnip pattern):
  cli.app       -> argument parsing and command dispatch
  cli.session   -> device discovery/selection and shell I/O (bridges to core/)
  cli.commands  -> one module per subcommand
  cli.ui        -> presentation helpers (banner, tables, help)
"""

__version__ = "1.0.0"
