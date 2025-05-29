import click
import os
import xml.etree.ElementTree as ET
import shutil
from pathlib import Path


# Define common MIME types that we want to find
COMMON_MIME_TYPES = {
    # Images
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", 
    "image/svg+xml", "image/bmp", "image/tiff", "image/tif",
    # Videos
    "video/mp4", "video/avi", "video/mov", "video/quicktime", "video/wmv", 
    "video/flv", "video/webm", "video/mkv",
    # Documents
    "application/pdf", "application/msword", 
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", 
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint", 
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Audio
    "audio/mp3", "audio/mpeg", "audio/wav", "audio/ogg", "audio/aac", "audio/m4a"
}


def find_asset_content_xml_files(base_path):
    """
    Recursively find all .content.xml files that are dam:Asset types with common MIME types.

    Args:
        base_path (Path): Base directory to search

    Returns:
        list: List of tuples (file_path, asset_path, mime_type) for dam:Asset files with common MIME types
    """
    asset_files = []

    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file == ".content.xml":
                file_path = Path(root) / file
                result = check_if_dam_asset_with_common_mime(file_path)
                if result:
                    asset_path, mime_type = result
                    asset_files.append((file_path, asset_path, mime_type))

    return asset_files


def check_if_dam_asset_with_common_mime(file_path):
    """
    Check if a .content.xml file has jcr:primaryType set to dam:Asset and has a common MIME type.

    Args:
        file_path (Path): Path to the .content.xml file

    Returns:
        tuple or None: (asset_path, mime_type) if it's a dam:Asset with common MIME type, None otherwise
    """
    try:
        # Parse the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Check if jcr:primaryType is dam:Asset
        primary_type = root.get("{http://www.jcp.org/jcr/1.0}primaryType")
        if primary_type == "dam:Asset":
            # Look for the metadata section to find MIME type
            mime_type = find_mime_type(root)
            if mime_type and mime_type in COMMON_MIME_TYPES:
                asset_path = get_asset_path(file_path)
                return (asset_path, mime_type)

    except Exception as e:
        click.echo(f"Error processing {file_path}: {e}")

    return None


def find_mime_type(root):
    """
    Find the dam:MIMEtype property in the asset's metadata section.

    Args:
        root: XML root element

    Returns:
        str or None: MIME type if found, None otherwise
    """
    # Look for jcr:content/metadata/dam:MIMEtype
    jcr_content = root.find("{http://www.jcp.org/jcr/1.0}content")
    if jcr_content is not None:
        metadata = jcr_content.find("metadata")
        if metadata is not None:
            mime_type = metadata.get("{http://www.day.com/dam/1.0}MIMEtype")
            return mime_type
    
    return None


def get_asset_path(file_path):
    """
    Get the asset path from the file location up to jcr_root.

    Args:
        file_path (Path): Path to the .content.xml file

    Returns:
        str: Asset path relative to jcr_root
    """
    # Convert to Path object if it's not already
    path = Path(file_path)
    
    # Get the directory containing the .content.xml file
    asset_dir = path.parent
    
    # Walk up the path to find jcr_root
    parts = []
    current = asset_dir
    
    while current.name != "jcr_root" and current != current.parent:
        parts.append(current.name)
        current = current.parent
    
    if current.name == "jcr_root":
        # Reverse the parts to get the correct order from jcr_root down
        parts.reverse()
        return "/" + "/".join(parts) if parts else "/"
    else:
        # If we didn't find jcr_root, return the relative path from the search base
        return str(asset_dir)


def find_jcr_root_directory(start_path):
    """
    Find the jcr_root directory by walking up the directory tree.

    Args:
        start_path (Path): Starting directory to search from

    Returns:
        Path or None: Path to jcr_root directory if found, None otherwise
    """
    current = Path(start_path).resolve()
    
    # First check if we're already in or under jcr_root
    while current != current.parent:
        if current.name == "jcr_root":
            return current
        
        # Check if jcr_root exists as a subdirectory
        jcr_root_path = current / "jcr_root"
        if jcr_root_path.exists() and jcr_root_path.is_dir():
            return jcr_root_path
            
        current = current.parent
    
    return None


def find_all_content_xml_files(jcr_root_path):
    """
    Find all .content.xml files in the jcr_root directory structure.

    Args:
        jcr_root_path (Path): Path to the jcr_root directory

    Returns:
        list: List of Path objects for all .content.xml files
    """
    content_xml_files = []
    
    for root, dirs, files in os.walk(jcr_root_path):
        for file in files:
            if file == ".content.xml":
                content_xml_files.append(Path(root) / file)
    
    return content_xml_files


def check_asset_references(asset_path, content_xml_files):
    """
    Check if an asset is referenced in any of the .content.xml files.

    Args:
        asset_path (str): The asset path to search for
        content_xml_files (list): List of .content.xml file paths to search in

    Returns:
        dict: Dictionary with reference info:
            - 'files': List of file paths where the asset is referenced
            - 'thumbnail_refs': List of files with dam:folderThumbnailPaths references
    """
    references = {'files': [], 'thumbnail_refs': []}
    
    for xml_file in content_xml_files:
        try:
            # Read file content as text for simple string search
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for asset path in image and fileReference properties
            if (f'image="{asset_path}"' in content or 
                f"image='{asset_path}'" in content or
                f'fileReference="{asset_path}"' in content or
                f"fileReference='{asset_path}'" in content):
                references['files'].append(xml_file)
            
            # Check for asset path in dam:folderThumbnailPaths
            elif f'dam:folderThumbnailPaths=' in content and asset_path in content:
                # More precise check for folderThumbnailPaths
                if check_folder_thumbnail_paths(xml_file, asset_path):
                    references['thumbnail_refs'].append(xml_file)
                
        except Exception as e:
            click.echo(f"Error checking references in {xml_file}: {e}")
    
    return references


def check_folder_thumbnail_paths(xml_file, asset_path):
    """
    Check if an asset path is referenced in dam:folderThumbnailPaths property.

    Args:
        xml_file (Path): Path to the XML file
        asset_path (str): Asset path to search for

    Returns:
        bool: True if asset is found in folderThumbnailPaths, False otherwise
    """
    try:
        # Parse the XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Look for jcr:content element
        jcr_content = root.find("{http://www.jcp.org/jcr/1.0}content")
        if jcr_content is not None:
            # Get the dam:folderThumbnailPaths attribute
            thumbnail_paths = jcr_content.get("{http://www.day.com/dam/1.0}folderThumbnailPaths")
            if thumbnail_paths:
                # Parse the array format [path1,path2,path3]
                if thumbnail_paths.startswith('[') and thumbnail_paths.endswith(']'):
                    paths_str = thumbnail_paths[1:-1]  # Remove brackets
                    paths = [path.strip() for path in paths_str.split(',') if path.strip()]
                    return asset_path in paths
    
    except Exception as e:
        click.echo(f"Error parsing folderThumbnailPaths in {xml_file}: {e}")
    
    return False


def clean_folder_thumbnail_paths(xml_file, asset_path):
    """
    Remove an asset path from dam:folderThumbnailPaths property in an XML file.

    Args:
        xml_file (Path): Path to the XML file
        asset_path (str): Asset path to remove

    Returns:
        bool: True if the file was modified, False otherwise
    """
    try:
        # Parse the XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Look for jcr:content element
        jcr_content = root.find("{http://www.jcp.org/jcr/1.0}content")
        if jcr_content is not None:
            # Get the dam:folderThumbnailPaths attribute
            thumbnail_paths = jcr_content.get("{http://www.day.com/dam/1.0}folderThumbnailPaths")
            if thumbnail_paths:
                # Parse the array format [path1,path2,path3]
                if thumbnail_paths.startswith('[') and thumbnail_paths.endswith(']'):
                    paths_str = thumbnail_paths[1:-1]  # Remove brackets
                    paths = [path.strip() for path in paths_str.split(',') if path.strip()]
                    
                    # Remove the asset path if it exists
                    if asset_path in paths:
                        paths.remove(asset_path)
                        
                        # Update the attribute
                        if paths:
                            # Reconstruct the array string
                            new_paths_str = '[' + ','.join(paths) + ']'
                            jcr_content.set("{http://www.day.com/dam/1.0}folderThumbnailPaths", new_paths_str)
                        else:
                            # Remove the attribute if no paths remain
                            del jcr_content.attrib["{http://www.day.com/dam/1.0}folderThumbnailPaths"]
                        
                        # Write the modified XML back to the file
                        tree.write(xml_file, encoding='utf-8', xml_declaration=True)
                        return True
    
    except Exception as e:
        click.echo(f"Error cleaning folderThumbnailPaths in {xml_file}: {e}")
    
    return False


def delete_asset_folder(asset_file_path, dry_run=True):
    """
    Delete the parent folder containing the asset's .content.xml file.

    Args:
        asset_file_path (Path): Path to the asset's .content.xml file
        dry_run (bool): If True, only show what would be deleted

    Returns:
        bool: True if deletion was successful or would be successful in dry run
    """
    # Get the parent directory of the .content.xml file
    asset_folder = asset_file_path.parent
    
    try:
        if dry_run:
            click.echo(f"  Would delete folder: {asset_folder}")
            return True
        else:
            shutil.rmtree(asset_folder)
            click.echo(f"  Deleted folder: {asset_folder}")
            return True
    except Exception as e:
        click.echo(f"  Error deleting {asset_folder}: {e}")
        return False


@click.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without actually deleting files")
def asset_remove_unused(path, dry_run):
    """Find and remove unused DAM assets with common MIME types.

    Walks recursively from the given path and searches for .content.xml files
    which have the jcr:primaryType set to dam:Asset and contain common MIME types
    (images, videos, documents, audio). For each found asset, checks if it's
    referenced in other .content.xml files via 'image' or 'fileReference' properties.
    
    Shows a summary of unused assets and asks for confirmation before deletion.
    Use --dry-run to preview what would be deleted without confirmation.

    Args:
        path: The path to start searching from (default: current directory)

    Examples:
    \b
        # Preview what would be deleted (no confirmation needed)
        aemcli asset-remove-unused content/dam --dry-run
        
        # Find and delete unused assets (asks for confirmation)
        aemcli asset-remove-unused /path/to/content
    """
    base_path = Path(path).resolve()
    
    if not base_path.exists():
        click.echo(f"Error: Path '{path}' does not exist")
        return
    
    if not base_path.is_dir():
        click.echo(f"Error: Path '{path}' is not a directory")
        return

    # Find the jcr_root directory
    jcr_root_path = find_jcr_root_directory(base_path)
    if not jcr_root_path:
        click.echo(f"Error: Could not find jcr_root directory in or above {base_path}")
        return

    click.echo(f"Searching for DAM assets with common MIME types in: {base_path}")
    click.echo(f"Using jcr_root directory: {jcr_root_path}")
    click.echo("-" * 70)

    # Find all dam:Asset files with common MIME types
    asset_files = find_asset_content_xml_files(base_path)
    
    if not asset_files:
        click.echo("No DAM assets with common MIME types found.")
        return

    # Find all .content.xml files in jcr_root for reference checking
    click.echo("Scanning for asset references...")
    all_content_xml_files = find_all_content_xml_files(jcr_root_path)
    click.echo(f"Found {len(all_content_xml_files)} .content.xml files to check for references")
    click.echo("-" * 70)

    # Check references for each asset
    unused_assets = []
    used_assets = []
    assets_with_thumbnail_refs = []
    
    for file_path, asset_path, mime_type in asset_files:
        references = check_asset_references(asset_path, all_content_xml_files)
        
        if references['files']:
            used_assets.append((file_path, asset_path, mime_type, references['files']))
            click.echo(f"USED: {asset_path} (MIME: {mime_type}) - {len(references['files'])} reference(s)")
        elif references['thumbnail_refs']:
            # Asset is only used in folderThumbnailPaths - mark for cleanup and deletion
            assets_with_thumbnail_refs.append((file_path, asset_path, mime_type, references['thumbnail_refs']))
            click.echo(f"THUMBNAIL ONLY: {asset_path} (MIME: {mime_type}) - {len(references['thumbnail_refs'])} folderThumbnailPaths reference(s)")
            # Mark for deletion (cleanup will happen after confirmation)
            unused_assets.append((file_path, asset_path, mime_type))
        else:
            unused_assets.append((file_path, asset_path, mime_type))
            click.echo(f"UNUSED: {asset_path} (MIME: {mime_type})")

    click.echo("-" * 70)
    click.echo(f"Summary:")
    click.echo(f"  Total assets found: {len(asset_files)}")
    click.echo(f"  Used assets: {len(used_assets)}")
    if assets_with_thumbnail_refs:
        click.echo(f"  Assets with only thumbnail references: {len(assets_with_thumbnail_refs)}")
    click.echo(f"  Unused assets: {len(unused_assets)}")

    # Handle deletion of unused assets
    if unused_assets:
        click.echo("-" * 70)
        if dry_run:
            click.echo("DRY RUN - The following folders would be deleted:")
            if assets_with_thumbnail_refs:
                click.echo("(Note: folderThumbnailPaths references will be cleaned up first)")
            
            deleted_count = 0
            for file_path, asset_path, mime_type in unused_assets:
                click.echo(f"Processing: {asset_path}")
                if delete_asset_folder(file_path, dry_run):
                    deleted_count += 1
            
            click.echo("-" * 70)
            click.echo(f"Would delete {deleted_count} unused asset folders")
            if assets_with_thumbnail_refs:
                click.echo(f"Would clean {len(assets_with_thumbnail_refs)} folderThumbnailPaths references")
        else:
            # Show summary and ask for confirmation
            click.echo("The following unused asset folders will be PERMANENTLY DELETED:")
            if assets_with_thumbnail_refs:
                click.echo("(folderThumbnailPaths references will be cleaned up first)")
            click.echo()
            for file_path, asset_path, mime_type in unused_assets:
                folder_path = file_path.parent
                click.echo(f"  • {asset_path} (MIME: {mime_type})")
                click.echo(f"    Folder: {folder_path}")
            
            click.echo()
            click.echo(f"Total: {len(unused_assets)} asset folder(s) will be deleted")
            if assets_with_thumbnail_refs:
                click.echo(f"Note: {len(assets_with_thumbnail_refs)} folderThumbnailPaths references will be cleaned up")
            click.echo()
            
            # Ask for confirmation
            if click.confirm("Do you want to proceed with the deletion?", default=False):
                click.echo("-" * 70)
                
                # First, clean up folderThumbnailPaths references
                if assets_with_thumbnail_refs:
                    click.echo("Cleaning folderThumbnailPaths references:")
                    total_cleaned = 0
                    for file_path, asset_path, mime_type, thumb_files in assets_with_thumbnail_refs:
                        cleaned_count = 0
                        for thumb_file in thumb_files:
                            if clean_folder_thumbnail_paths(thumb_file, asset_path):
                                cleaned_count += 1
                        click.echo(f"  CLEANED: {asset_path} - removed from {cleaned_count} folderThumbnailPaths")
                        total_cleaned += cleaned_count
                    click.echo(f"  Total: Cleaned {total_cleaned} folderThumbnailPaths references")
                    click.echo("-" * 70)
                
                # Then delete asset folders
                click.echo("Deleting unused asset folders:")
                deleted_count = 0
                for file_path, asset_path, mime_type in unused_assets:
                    click.echo(f"Processing: {asset_path}")
                    if delete_asset_folder(file_path, dry_run):
                        deleted_count += 1
                
                click.echo("-" * 70)
                click.echo(f"Deleted {deleted_count} unused asset folders")
                if assets_with_thumbnail_refs:
                    click.echo(f"Cleaned {len(assets_with_thumbnail_refs)} folderThumbnailPaths references")
            else:
                click.echo("Deletion cancelled by user.")
    else:
        click.echo("\nNo unused assets found to delete.") 