import click
from .commands.content_cleanup import content_cleanup
from .commands.repo import repo
from .commands.asset_remove_unused import asset_remove_unused


@click.group()
def main():
    """AEM-CLI: a tool with special subcommands."""
    pass


# register subcommands
main.add_command(content_cleanup)
main.add_command(repo)
main.add_command(asset_remove_unused)

if __name__ == "__main__":
    main()
