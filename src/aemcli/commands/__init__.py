"""
Subcommands for the aemcli tool.
"""

# import each command here to simplify registration
from .content_cleanup import content_cleanup
from .repo import repo

__all__ = ["content_cleanup", "repo"]
