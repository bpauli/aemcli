import click
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import re


def get_default_properties():
    """Get the default set of properties to remove."""
    return {
        'cq:isDelivered',
        'cq:lastModified',
        'cq:lastModifiedBy',
        'cq:lastReplicated',
        'cq:lastReplicated_publish',
        'cq:lastReplicatedBy',
        'cq:lastReplicatedBy_publish',
        'cq:lastReplicationAction',
        'cq:lastReplicationAction_publish',
        'jcr:isCheckedOut',
        'jcr:lastModified',
        'jcr:lastModifiedBy',
        'jcr:uuid'
    }


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
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        modified = False
        
        # Remove properties using regex patterns
        for prop in properties_to_remove:
            # Pattern to match the property and its value
            # This handles various formats: prop="value", prop="{Type}value", etc.
            pattern = rf'\s+{re.escape(prop)}="[^"]*"'
            if re.search(pattern, content):
                content = re.sub(pattern, '', content)
                modified = True
                click.echo(f"  Removed property: {prop}")
        
        if modified and not dry_run:
            # Write the cleaned content back to file
            with open(file_path, 'w', encoding='utf-8') as f:
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
            if file == '.content.xml':
                content_xml_files.append(Path(root) / file)
    
    return content_xml_files


@click.command()
@click.argument('path', type=click.Path(exists=True), default='content/sites-franklin-commerce')
@click.option('--dry-run', is_flag=True, help='Show what would be changed without actually modifying files')
@click.option('--default', 'use_default', is_flag=True, help='Include default AEM properties in removal list')
@click.argument('properties', nargs=-1)
def content_cleanup(path, dry_run, use_default, properties):
    """Clean .content.xml files by removing specified properties.
    
    By default, if no properties are specified and --default is not used,
    the command will use the default set of AEM properties.
    
    Examples:
    \b
      # Use default properties
      aemcli content-cleanup
      aemcli content-cleanup --default
    
    \b
      # Use only custom properties
      aemcli content-cleanup /path cq:customProp jcr:myProp
    
    \b
      # Combine default and custom properties
      aemcli content-cleanup --default cq:customProp jcr:myProp
    
    Default properties removed:
    - cq:isDelivered, cq:lastModified, cq:lastModifiedBy
    - cq:lastReplicated*, cq:lastReplicatedBy*, cq:lastReplicationAction*
    - jcr:isCheckedOut, jcr:lastModified, jcr:lastModifiedBy, jcr:uuid
    """
    base_path = Path(path)
    
    if not base_path.exists():
        click.echo(f"✗ Error: Directory {base_path} does not exist")
        raise click.Abort()
    
    # Determine which properties to remove
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
    
    # Process each file
    modified_count = 0
    total_count = len(content_xml_files)
    
    click.echo(f"\nProcessing {total_count} files...")
    click.echo("-" * 50)
    
    for file_path in content_xml_files:
        if clean_xml_file(file_path, properties_to_remove, dry_run):
            modified_count += 1
    
    click.echo("-" * 50)
    click.echo("Summary:")
    click.echo(f"  Total files processed: {total_count}")
    if dry_run:
        click.echo(f"  Files that would be modified: {modified_count}")
        click.echo(f"  Files that would remain unchanged: {total_count - modified_count}")
    else:
        click.echo(f"  Files modified: {modified_count}")
        click.echo(f"  Files unchanged: {total_count - modified_count}")