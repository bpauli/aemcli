import click
from .commands.content_cleanup import content_cleanup


@click.group()
def main():
    """AEM-CLI: a tool with special subcommands."""
    pass


# register subcommands
main.add_command(content_cleanup)

if __name__ == "__main__":
    main()
