"""
Subcommands for the aemcli tool.
"""

# import each command here to simplify registration
from .content_cleanup import content_cleanup

__all__ = ["content_cleanup"]