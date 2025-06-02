import click
import os
from pathlib import Path
import re
import shutil


def get_default_properties():
    """Get the default set of properties to remove."""
    return {
        "cq:isDelivered",
        "cq:lastModified",
        "cq:lastModifiedBy",
        "cq:lastReplicated",
        "cq:lastReplicated_preview",
        "cq:lastReplicated_publish",
        "cq:lastReplicated_scene7",
        "cq:lastReplicatedBy",
        "cq:lastReplicatedBy_preview",
        "cq:lastReplicatedBy_publish",
        "cq:lastReplicatedBy_scene7",
        "cq:lastReplicationAction",
        "cq:lastReplicationAction_preview",
        "cq:lastReplicationAction_publish",
        "cq:lastReplicationAction_scene7",
        "jcr:isCheckedOut",
        "jcr:lastModified",
        "jcr:lastModifiedBy",
        "jcr:uuid",
    }


def mangle_node_name(node_name):
    """
    Convert a JCR node name to its filesystem representation.
    
    JCR node names with colons are mangled in the filesystem:
    - jcr:content becomes _jcr_content
    - rep:policy becomes _rep_policy
    
    Args:
        node_name (str): The JCR node name
        
    Returns:
        str: The mangled filesystem name
    """
    if ":" in node_name:
        return "_" + node_name.replace(":", "_")
    return node_name


def unmangle_node_name(mangled_name):
    """
    Convert a filesystem node name back to JCR representation.
    
    Args:
        mangled_name (str): The mangled filesystem name
        
    Returns:
        str: The JCR node name
    """
    # Handle the case where names start with underscore (mangled names)
    if mangled_name.startswith("_") and "_" in mangled_name[1:]:
        # Find the second underscore and replace with colon
        parts = mangled_name[1:].split("_", 1)
        if len(parts) == 2:
            return f"{parts[0]}:{parts[1]}"
    return mangled_name


def clean_xml_file(file_path, properties_to_remove, dry_run=False):
    """
    Clean a single .content.xml file by removing specified properties.

    Args:
        file_path (Path): Path to the .content.xml file
        properties_to_remove (set): Set of property names to remove
        dry_run (bool): If True, show what would be changed without modifying files

    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        # Read the file content as text first
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        modified = False

        # Remove properties using regex patterns
        for prop in properties_to_remove:
            # Pattern to match the property and its value
            # This handles various formats: prop="value", prop="{Type}value", etc.
            pattern = rf'\s+{re.escape(prop)}="[^"]*"'
            if re.search(pattern, content):
                content = re.sub(pattern, "", content)
                modified = True
                click.echo(f"  Removed property: {prop}")

        if modified and not dry_run:
            # Write the cleaned content back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            click.echo(f"✓ Cleaned: {file_path}")
            return True
        elif modified and dry_run:
            click.echo(f"Would clean: {file_path}")
            return True
        else:
            click.echo(f"- No changes needed: {file_path}")
            return False

    except Exception as e:
        click.echo(f"✗ Error processing file {file_path}: {e}")
        return False


def remove_node_from_xml(file_path, node_name, dry_run=False):
    """
    Remove a node from a .content.xml file.

    Args:
        file_path (Path): Path to the .content.xml file
        node_name (str): Name of the node to remove
        dry_run (bool): If True, show what would be changed without modifying files

    Returns:
        bool: True if file was modified, False otherwise
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        modified = False

        # Pattern to match the entire node element
        # This handles self-closing tags and tags with content
        escaped_node = re.escape(node_name)
        
        # Pattern for self-closing tags: <nodeName ... />
        self_closing_pattern = rf'<{escaped_node}[^>]*\/>'
        
        # Pattern for tags with content: <nodeName ...>...</nodeName>
        # This is more complex as we need to handle nested tags properly
        opening_tag_pattern = rf'<{escaped_node}[^>]*>'
        closing_tag_pattern = rf'<\/{escaped_node}>'
        
        # First try self-closing tags
        if re.search(self_closing_pattern, content, re.DOTALL):
            content = re.sub(self_closing_pattern, "", content, flags=re.DOTALL)
            modified = True
            click.echo(f"  Removed self-closing node: {node_name}")
        
        # Then try tags with content (this is trickier due to potential nesting)
        # For now, let's handle simple cases without nested nodes of the same name
        full_node_pattern = rf'<{escaped_node}[^>]*>.*?<\/{escaped_node}>'
        if re.search(full_node_pattern, content, re.DOTALL):
            content = re.sub(full_node_pattern, "", content, flags=re.DOTALL)
            modified = True
            click.echo(f"  Removed node with content: {node_name}")

        # Clean up any extra whitespace that might be left
        if modified:
            # Remove empty lines that might be left behind
            content = re.sub(r'\n\s*\n', '\n', content)

        if modified and not dry_run:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            click.echo(f"✓ Cleaned: {file_path}")
            return True
        elif modified and dry_run:
            click.echo(f"Would clean: {file_path}")
            return True
        else:
            click.echo(f"- No changes needed: {file_path}")
            return False

    except Exception as e:
        click.echo(f"✗ Error processing file {file_path}: {e}")
        return False


def find_content_xml_files(base_path):
    """
    Recursively find all .content.xml files in the given directory.

    Args:
        base_path (Path): Base directory to search

    Returns:
        list: List of Path objects for .content.xml files
    """
    content_xml_files = []

    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file == ".content.xml":
                content_xml_files.append(Path(root) / file)

    return content_xml_files


def find_node_folders(base_path, node_name):
    """
    Recursively find all folders with the given node name (considering name mangling).

    Args:
        base_path (Path): Base directory to search
        node_name (str): Name of the node to find

    Returns:
        list: List of Path objects for matching folders
    """
    folders = []
    mangled_name = mangle_node_name(node_name)
    
    for root, dirs, files in os.walk(base_path):
        # Check if any directory matches the node name or its mangled version
        for dir_name in dirs:
            if dir_name == node_name or dir_name == mangled_name:
                folders.append(Path(root) / dir_name)
    
    return folders


def determine_properties_to_remove(use_default, properties):
    """
    Determine which properties to remove based on flags and arguments.

    Args:
        use_default (bool): Whether to include default properties
        properties (tuple): Custom properties to remove

    Returns:
        set: Set of property names to remove
    """
    properties_to_remove = set()

    # If no custom properties and no --default flag, use default behavior
    if not properties and not use_default:
        properties_to_remove = get_default_properties()
        click.echo("Using default AEM properties for removal")
    else:
        # Add default properties if --default flag is used
        if use_default:
            properties_to_remove.update(get_default_properties())
            click.echo("Including default AEM properties")

        # Add custom properties
        if properties:
            properties_to_remove.update(properties)
            click.echo(f"Including custom properties: {', '.join(properties)}")

    return properties_to_remove


def process_files_for_properties(content_xml_files, properties_to_remove, dry_run):
    """
    Process all content XML files for property removal and return summary statistics.

    Args:
        content_xml_files (list): List of file paths to process
        properties_to_remove (set): Set of property names to remove
        dry_run (bool): Whether this is a dry run

    Returns:
        tuple: (modified_count, total_count)
    """
    modified_count = 0
    total_count = len(content_xml_files)

    click.echo(f"\nProcessing {total_count} files for property removal...")
    click.echo("-" * 50)

    for file_path in content_xml_files:
        if clean_xml_file(file_path, properties_to_remove, dry_run):
            modified_count += 1

    return modified_count, total_count


def process_files_for_nodes(content_xml_files, node_name, dry_run):
    """
    Process all content XML files for node removal and return summary statistics.

    Args:
        content_xml_files (list): List of file paths to process
        node_name (str): Name of the node to remove
        dry_run (bool): Whether this is a dry run

    Returns:
        tuple: (modified_count, total_count)
    """
    modified_count = 0
    total_count = len(content_xml_files)

    click.echo(f"\nProcessing {total_count} files for node removal...")
    click.echo("-" * 50)

    for file_path in content_xml_files:
        if remove_node_from_xml(file_path, node_name, dry_run):
            modified_count += 1

    return modified_count, total_count


def remove_node_folders(folders, dry_run):
    """
    Remove node folders and return summary statistics.

    Args:
        folders (list): List of folder paths to remove
        dry_run (bool): Whether this is a dry run

    Returns:
        tuple: (removed_count, total_count)
    """
    removed_count = 0
    total_count = len(folders)

    if total_count > 0:
        click.echo(f"\nProcessing {total_count} folders for removal...")
        click.echo("-" * 50)

        for folder_path in folders:
            try:
                if not dry_run:
                    shutil.rmtree(folder_path)
                    click.echo(f"✓ Removed folder: {folder_path}")
                else:
                    click.echo(f"Would remove folder: {folder_path}")
                removed_count += 1
            except Exception as e:
                click.echo(f"✗ Error removing folder {folder_path}: {e}")

    return removed_count, total_count


def print_summary(modified_count, total_count, dry_run, operation="processed"):
    """
    Print the summary of the cleanup operation.

    Args:
        modified_count (int): Number of files modified
        total_count (int): Total number of files processed
        dry_run (bool): Whether this was a dry run
        operation (str): Description of the operation
    """
    click.echo("-" * 50)
    click.echo("Summary:")
    click.echo(f"  Total files {operation}: {total_count}")
    if dry_run:
        click.echo(f"  Files that would be modified: {modified_count}")
        click.echo(
            f"  Files that would remain unchanged: {total_count - modified_count}"
        )
    else:
        click.echo(f"  Files modified: {modified_count}")
        click.echo(f"  Files unchanged: {total_count - modified_count}")


@click.group()
def content_cleanup():
    """Clean .content.xml files and remove nodes/folders."""
    pass


@content_cleanup.command()
@click.argument(
    "path", type=click.Path(exists=True), default="content/sites-franklin-commerce"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without actually modifying files",
)
@click.option(
    "--default",
    "use_default",
    is_flag=True,
    help="Include default AEM properties in removal list",
)
@click.argument("properties", nargs=-1)
def property(path, dry_run, use_default, properties):
    """Clean .content.xml files by removing specified properties.

    By default, if no properties are specified and --default is not used,
    the command will use the default set of AEM properties.

    Examples:
    \b
      # Use default properties
      aemcli content-cleanup property
      aemcli content-cleanup property --default

    \b
      # Use only custom properties
      aemcli content-cleanup property /path cq:customProp jcr:myProp

    \b
      # Combine default and custom properties
      aemcli content-cleanup property --default cq:customProp jcr:myProp

    Default properties removed:
    - cq:isDelivered, cq:lastModified, cq:lastModifiedBy
    - cq:lastReplicated*, cq:lastReplicatedBy*, cq:lastReplicationAction*
    - jcr:isCheckedOut, jcr:lastModified, jcr:lastModifiedBy, jcr:uuid
    """
    base_path = Path(path)

    if not base_path.exists():
        click.echo(f"✗ Error: Path '{path}' does not exist")
        raise click.Abort()

    # Determine which properties to remove
    properties_to_remove = determine_properties_to_remove(use_default, properties)

    if not properties_to_remove:
        click.echo("✗ Error: No properties specified for removal")
        raise click.Abort()

    click.echo(f"\nProperties to remove: {', '.join(sorted(properties_to_remove))}")
    click.echo(f"Searching for .content.xml files in: {base_path}")

    # Find all .content.xml files
    content_xml_files = find_content_xml_files(base_path)

    if not content_xml_files:
        click.echo("No .content.xml files found")
        return

    click.echo(f"Found {len(content_xml_files)} .content.xml files")

    if dry_run:
        click.echo("\n--- DRY RUN MODE - No files will be modified ---")

    # Process files and get summary
    modified_count, total_count = process_files_for_properties(
        content_xml_files, properties_to_remove, dry_run
    )

    # Print summary
    print_summary(modified_count, total_count, dry_run)


@content_cleanup.command()
@click.argument("node_name", required=True)
@click.argument(
    "path", type=click.Path(exists=True), default="."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without actually modifying files",
)
def node(node_name, path, dry_run):
    """Remove nodes from .content.xml files and delete corresponding folders.

    This command removes nodes with the specified name from all .content.xml files
    and also removes any folders with that name. Node name mangling is handled
    automatically (e.g., jcr:content becomes _jcr_content in the filesystem).

    Examples:
    \b
      # Remove jcr:content nodes and folders from current directory
      aemcli content-cleanup node jcr:content

    \b
      # Remove cq:dialog nodes and folders with dry run
      aemcli content-cleanup node cq:dialog --dry-run

    \b
      # Remove nodes from specific path
      aemcli content-cleanup node rep:policy /path/to/content
    """
    base_path = Path(path)

    if not base_path.exists():
        click.echo(f"✗ Error: Path '{path}' does not exist")
        raise click.Abort()

    click.echo(f"\nNode to remove: {node_name}")
    click.echo(f"Mangled folder name: {mangle_node_name(node_name)}")
    click.echo(f"Searching in: {base_path}")

    if dry_run:
        click.echo("\n--- DRY RUN MODE - No files or folders will be modified ---")

    # Find all .content.xml files
    content_xml_files = find_content_xml_files(base_path)
    
    if content_xml_files:
        click.echo(f"Found {len(content_xml_files)} .content.xml files")
        # Process files for node removal
        modified_count, total_count = process_files_for_nodes(
            content_xml_files, node_name, dry_run
        )
        print_summary(modified_count, total_count, dry_run)
    else:
        click.echo("No .content.xml files found")

    # Find and remove node folders
    node_folders = find_node_folders(base_path, node_name)
    
    if node_folders:
        removed_count, folder_count = remove_node_folders(node_folders, dry_run)
        
        click.echo("-" * 50)
        click.echo("Folder Summary:")
        click.echo(f"  Total folders found: {folder_count}")
        if dry_run:
            click.echo(f"  Folders that would be removed: {removed_count}")
        else:
            click.echo(f"  Folders removed: {removed_count}")
    else:
        click.echo(f"\nNo folders found with name '{node_name}' or '{mangle_node_name(node_name)}'")
