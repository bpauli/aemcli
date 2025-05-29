import click
from .commands.content_cleanup import content_cleanup
from .commands.repo import repo


@click.group()
def main():
    """AEM-CLI: a tool with special subcommands."""
    pass


# register subcommands
main.add_command(content_cleanup)
main.add_command(repo)

if __name__ == "__main__":
    main()
