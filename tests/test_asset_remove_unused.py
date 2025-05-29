import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from aemcli.commands.asset_remove_unused import (
    asset_remove_unused,
    find_asset_content_xml_files,
    check_if_dam_asset_with_common_mime,
    get_asset_path,
    find_mime_type,
    find_jcr_root_directory,
    find_all_content_xml_files,
    check_asset_references,
    delete_asset_folder,
    check_folder_thumbnail_paths,
    clean_folder_thumbnail_paths,
    COMMON_MIME_TYPES,
)


class TestAssetRemoveUnused:
    """Test suite for asset-remove-unused command."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()
        self.test_data_dir = Path(__file__).parent / "test_content" / "asset_remove_unused"

    def test_asset_remove_unused_find_assets_with_references(self):
        """Test that asset-remove-unused correctly identifies used and unused assets."""
        result = self.runner.invoke(asset_remove_unused, [str(self.test_data_dir)])

        assert result.exit_code == 0
        assert "Searching for DAM assets with common MIME types in:" in result.output
        assert "Using jcr_root directory:" in result.output
        assert "Scanning for asset references..." in result.output
        
        # Should show both assets as USED since they're referenced in page_with_reference
        assert "USED: /content/dam/asset1 (MIME: image/jpeg)" in result.output
        assert "USED: /content/dam/folder/asset2 (MIME: image/png)" in result.output
        
        # Should not find asset3 with uncommon MIME type
        assert "/content/dam/uncommon/asset3" not in result.output
        
        # Summary should show correct counts
        assert "Total assets found: 2" in result.output
        assert "Used assets: 2" in result.output
        assert "Unused assets: 0" in result.output
        
        # Should show no unused assets found
        assert "No unused assets found to delete." in result.output

    def test_asset_remove_unused_with_unused_assets(self):
        """Test finding unused assets when no references exist."""
        with self.runner.isolated_filesystem():
            # Create test structure without references
            os.makedirs("test_dir/jcr_root/content/dam/test")
            os.makedirs("test_dir/jcr_root/content/pages/empty")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/test/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/jpeg"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            # Create a page without asset references
            with open("test_dir/jcr_root/content/pages/empty/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:cq="http://www.day.com/jcr/cq/1.0"
    jcr:primaryType="cq:Page">
</jcr:root>""")

            result = self.runner.invoke(asset_remove_unused, ["test_dir", "--dry-run"])

            assert result.exit_code == 0
            assert "UNUSED: /content/dam/test (MIME: image/jpeg)" in result.output
            assert "Total assets found: 1" in result.output
            assert "Used assets: 0" in result.output
            assert "Unused assets: 1" in result.output
            assert "DRY RUN - The following folders would be deleted:" in result.output
            
            # Verify folder still exists after dry run
            assert Path("test_dir/jcr_root/content/dam/test").exists()

    def test_asset_remove_unused_dry_run_deletion(self):
        """Test dry run deletion functionality."""
        with self.runner.isolated_filesystem():
            # Create test structure with unused asset
            os.makedirs("test_dir/jcr_root/content/dam/unused")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/unused/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/png"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            result = self.runner.invoke(asset_remove_unused, ["test_dir", "--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN - The following folders would be deleted:" in result.output
            assert "Would delete folder:" in result.output
            assert "Would delete 1 unused asset folders" in result.output
            
            # Verify folder still exists after dry run
            assert Path("test_dir/jcr_root/content/dam/unused").exists()

    def test_asset_remove_unused_actual_deletion(self):
        """Test actual deletion functionality with confirmation."""
        with self.runner.isolated_filesystem():
            # Create test structure with unused asset
            os.makedirs("test_dir/jcr_root/content/dam/todelete")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/todelete/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/gif"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            # Verify folder exists before deletion
            assert Path("test_dir/jcr_root/content/dam/todelete").exists()

            # Test with confirmation 'y'
            result = self.runner.invoke(asset_remove_unused, ["test_dir"], input='y\n')

            assert result.exit_code == 0
            assert "The following unused asset folders will be PERMANENTLY DELETED:" in result.output
            assert "/content/dam/todelete (MIME: image/gif)" in result.output
            assert "Total: 1 asset folder(s) will be deleted" in result.output
            assert "Do you want to proceed with the deletion?" in result.output
            assert "Deleting unused asset folders:" in result.output
            assert "Deleted folder:" in result.output
            assert "Deleted 1 unused asset folders" in result.output
            
            # Verify folder was actually deleted
            assert not Path("test_dir/jcr_root/content/dam/todelete").exists()

    def test_asset_remove_unused_deletion_cancelled(self):
        """Test deletion cancellation when user responds 'n'."""
        with self.runner.isolated_filesystem():
            # Create test structure with unused asset
            os.makedirs("test_dir/jcr_root/content/dam/cancelled")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/cancelled/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/png"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            # Verify folder exists before attempting deletion
            assert Path("test_dir/jcr_root/content/dam/cancelled").exists()

            # Test with confirmation 'n' (cancelled)
            result = self.runner.invoke(asset_remove_unused, ["test_dir"], input='n\n')

            assert result.exit_code == 0
            assert "The following unused asset folders will be PERMANENTLY DELETED:" in result.output
            assert "/content/dam/cancelled (MIME: image/png)" in result.output
            assert "Do you want to proceed with the deletion?" in result.output
            assert "Deletion cancelled by user." in result.output
            
            # Verify folder still exists after cancellation
            assert Path("test_dir/jcr_root/content/dam/cancelled").exists()

    def test_asset_remove_unused_no_assets(self):
        """Test asset-remove-unused when no DAM assets with common MIME types are found."""
        with self.runner.isolated_filesystem():
            # Create directory with non-DAM assets only
            os.makedirs("test_dir/jcr_root/content/pages")
            
            # Create a non-DAM .content.xml file
            with open("test_dir/jcr_root/content/pages/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:cq="http://www.day.com/jcr/cq/1.0"
    jcr:primaryType="cq:Page">
</jcr:root>""")

            result = self.runner.invoke(asset_remove_unused, ["test_dir"])

            assert result.exit_code == 0
            assert "No DAM assets with common MIME types found." in result.output

    def test_asset_remove_unused_nonexistent_path(self):
        """Test asset-remove-unused with non-existent path."""
        result = self.runner.invoke(asset_remove_unused, ["nonexistent_path"])

        # Click path validation returns exit code 2 for invalid paths
        assert result.exit_code == 2
        assert "Path 'nonexistent_path' does not exist" in result.output

    def test_asset_remove_unused_file_path(self):
        """Test asset-remove-unused with a file path instead of directory."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_file = f.name

        try:
            result = self.runner.invoke(asset_remove_unused, [temp_file])

            assert result.exit_code == 0
            assert "Error: Path" in result.output
            assert "is not a directory" in result.output

        finally:
            os.unlink(temp_file)

    def test_find_jcr_root_directory_function(self):
        """Test the find_jcr_root_directory function directly."""
        # Test with our test data directory
        jcr_root = find_jcr_root_directory(self.test_data_dir)
        assert jcr_root is not None
        assert jcr_root.name == "jcr_root"
        
        # Test with a path that doesn't contain jcr_root
        with tempfile.TemporaryDirectory() as temp_dir:
            result = find_jcr_root_directory(temp_dir)
            assert result is None

    def test_find_all_content_xml_files_function(self):
        """Test the find_all_content_xml_files function directly."""
        jcr_root = find_jcr_root_directory(self.test_data_dir)
        content_files = find_all_content_xml_files(jcr_root)
        
        # Should find multiple .content.xml files
        assert len(content_files) >= 4  # assets + pages + components + page_with_reference
        
        # All should be .content.xml files
        for file_path in content_files:
            assert file_path.name == ".content.xml"

    def test_check_asset_references_function(self):
        """Test the check_asset_references function directly."""
        jcr_root = find_jcr_root_directory(self.test_data_dir)
        content_files = find_all_content_xml_files(jcr_root)
        
        # Test asset1 which should be referenced
        references = check_asset_references("/content/dam/asset1", content_files)
        assert len(references['files']) > 0
        assert len(references['thumbnail_refs']) == 0
        
        # Test asset2 which should be referenced
        references = check_asset_references("/content/dam/folder/asset2", content_files)
        assert len(references['files']) > 0
        assert len(references['thumbnail_refs']) == 0
        
        # Test non-existent asset
        references = check_asset_references("/content/dam/nonexistent", content_files)
        assert len(references['files']) == 0
        assert len(references['thumbnail_refs']) == 0

    def test_delete_asset_folder_function(self):
        """Test the delete_asset_folder function directly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test asset folder
            asset_folder = Path(temp_dir) / "test_asset"
            asset_folder.mkdir()
            asset_file = asset_folder / ".content.xml"
            asset_file.write_text("test content")
            
            # Test dry run
            result = delete_asset_folder(asset_file, dry_run=True)
            assert result is True
            assert asset_folder.exists()  # Should still exist after dry run
            
            # Test actual deletion
            result = delete_asset_folder(asset_file, dry_run=False)
            assert result is True
            assert not asset_folder.exists()  # Should be deleted

    def test_find_asset_content_xml_files_function(self):
        """Test the find_asset_content_xml_files function directly."""
        asset_files = find_asset_content_xml_files(self.test_data_dir)

        assert len(asset_files) == 2
        
        # Extract asset paths and MIME types for easier assertion
        asset_data = [(asset_path, mime_type) for _, asset_path, mime_type in asset_files]
        
        assert ("/content/dam/asset1", "image/jpeg") in asset_data
        assert ("/content/dam/folder/asset2", "image/png") in asset_data
        # Should not include asset3 with uncommon MIME type
        assert any("/content/dam/uncommon/asset3" in path for path, _ in asset_data) == False

    def test_check_if_dam_asset_with_common_mime_function(self):
        """Test the check_if_dam_asset_with_common_mime function directly."""
        # Test with actual DAM asset with common MIME type
        dam_asset_file = self.test_data_dir / "jcr_root" / "content" / "dam" / "asset1" / ".content.xml"
        result = check_if_dam_asset_with_common_mime(dam_asset_file)
        assert result == ("/content/dam/asset1", "image/jpeg")

        # Test with DAM asset with uncommon MIME type
        uncommon_asset_file = self.test_data_dir / "jcr_root" / "content" / "dam" / "uncommon" / "asset3" / ".content.xml"
        result = check_if_dam_asset_with_common_mime(uncommon_asset_file)
        assert result is None

        # Test with non-DAM asset (page)
        page_file = self.test_data_dir / "jcr_root" / "content" / "pages" / "page1" / ".content.xml"
        result = check_if_dam_asset_with_common_mime(page_file)
        assert result is None

        # Test with non-DAM asset (component)
        component_file = self.test_data_dir / "jcr_root" / "content" / "components" / "component1" / ".content.xml"
        result = check_if_dam_asset_with_common_mime(component_file)
        assert result is None

    def test_get_asset_path_function(self):
        """Test the get_asset_path function directly."""
        # Test with nested asset path
        file_path = Path("/some/path/jcr_root/content/dam/folder/asset/.content.xml")
        result = get_asset_path(file_path)
        assert result == "/content/dam/folder/asset"

        # Test with root level asset
        file_path = Path("/some/path/jcr_root/content/dam/asset/.content.xml")
        result = get_asset_path(file_path)
        assert result == "/content/dam/asset"

        # Test without jcr_root in path
        file_path = Path("/some/other/path/content/dam/asset/.content.xml")
        result = get_asset_path(file_path)
        assert "/content/dam/asset" in str(result)

    def test_find_mime_type_function(self):
        """Test the find_mime_type function directly."""
        # Parse a test asset and extract MIME type
        dam_asset_file = self.test_data_dir / "jcr_root" / "content" / "dam" / "asset1" / ".content.xml"
        import xml.etree.ElementTree as ET
        tree = ET.parse(dam_asset_file)
        root = tree.getroot()
        
        mime_type = find_mime_type(root)
        assert mime_type == "image/jpeg"

    def test_common_mime_types_constant(self):
        """Test that common MIME types constant contains expected types."""
        assert "image/jpeg" in COMMON_MIME_TYPES
        assert "image/png" in COMMON_MIME_TYPES
        assert "video/mp4" in COMMON_MIME_TYPES
        assert "application/pdf" in COMMON_MIME_TYPES
        assert "audio/mp3" in COMMON_MIME_TYPES
        # Should not include uncommon types
        assert "application/vnd.adobe.indesign-idml" not in COMMON_MIME_TYPES

    def test_help_output(self):
        """Test that help output is correctly displayed."""
        result = self.runner.invoke(asset_remove_unused, ["--help"])

        assert result.exit_code == 0
        assert "Find and remove unused DAM assets with common MIME types" in result.output
        assert "Shows a summary of unused assets and asks for confirmation before deletion" in result.output
        assert "--dry-run" in result.output
        assert "--delete-unused" not in result.output
        assert "Examples:" in result.output

    def test_check_folder_thumbnail_paths_function(self):
        """Test the check_folder_thumbnail_paths function directly."""
        with self.runner.isolated_filesystem():
            # Create test XML file with folderThumbnailPaths
            os.makedirs("test_folder")
            xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="nt:file">
    <jcr:content
        dam:folderThumbnailPaths="[/content/dam/asset1,/content/dam/asset2,/content/dam/asset3]"
        jcr:primaryType="nt:unstructured"/>
</jcr:root>'''
            
            with open("test_folder/.content.xml", "w") as f:
                f.write(xml_content)
            
            # Test asset that exists in folderThumbnailPaths
            assert check_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/asset2") == True
            
            # Test asset that doesn't exist
            assert check_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/nonexistent") == False

    def test_clean_folder_thumbnail_paths_function(self):
        """Test the clean_folder_thumbnail_paths function directly."""
        with self.runner.isolated_filesystem():
            # Create test XML file with folderThumbnailPaths
            os.makedirs("test_folder")
            xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="nt:file">
    <jcr:content
        dam:folderThumbnailPaths="[/content/dam/asset1,/content/dam/asset2,/content/dam/asset3]"
        jcr:primaryType="nt:unstructured"/>
</jcr:root>'''
            
            with open("test_folder/.content.xml", "w") as f:
                f.write(xml_content)
            
            # Clean one asset
            result = clean_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/asset2")
            assert result == True
            
            # Verify the asset was removed
            assert check_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/asset2") == False
            
            # Verify other assets are still there
            assert check_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/asset1") == True
            assert check_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/asset3") == True

    def test_clean_folder_thumbnail_paths_remove_all(self):
        """Test cleaning all paths from folderThumbnailPaths."""
        with self.runner.isolated_filesystem():
            # Create test XML file with single folderThumbnailPath
            os.makedirs("test_folder")
            xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="nt:file">
    <jcr:content
        dam:folderThumbnailPaths="[/content/dam/only-asset]"
        jcr:primaryType="nt:unstructured"/>
</jcr:root>'''
            
            with open("test_folder/.content.xml", "w") as f:
                f.write(xml_content)
            
            # Clean the only asset
            result = clean_folder_thumbnail_paths("test_folder/.content.xml", "/content/dam/only-asset")
            assert result == True
            
            # Verify the entire attribute was removed
            import xml.etree.ElementTree as ET
            tree = ET.parse("test_folder/.content.xml")
            root = tree.getroot()
            jcr_content = root.find("{http://www.jcp.org/jcr/1.0}content")
            thumbnail_paths = jcr_content.get("{http://www.day.com/dam/1.0}folderThumbnailPaths")
            assert thumbnail_paths is None

    def test_asset_with_folder_thumbnail_paths_references(self):
        """Test asset-remove-unused with assets referenced only in folderThumbnailPaths."""
        with self.runner.isolated_filesystem():
            # Create test structure
            os.makedirs("test_dir/jcr_root/content/dam/thumbnail_only")
            os.makedirs("test_dir/jcr_root/content/folder")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/thumbnail_only/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/jpeg"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            # Create a folder that references the asset in folderThumbnailPaths
            with open("test_dir/jcr_root/content/folder/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="nt:file">
    <jcr:content
        dam:folderThumbnailPaths="[/content/dam/thumbnail_only,/content/dam/other]"
        jcr:primaryType="nt:unstructured"/>
</jcr:root>""")

            # Test dry run
            result = self.runner.invoke(asset_remove_unused, ["test_dir", "--dry-run"])

            assert result.exit_code == 0
            assert "THUMBNAIL ONLY: /content/dam/thumbnail_only (MIME: image/jpeg)" in result.output
            assert "Assets with only thumbnail references: 1" in result.output
            assert "Would clean 1 folderThumbnailPaths references" in result.output
            
            # Verify folder still exists and reference is still there after dry run
            assert Path("test_dir/jcr_root/content/dam/thumbnail_only").exists()
            assert check_folder_thumbnail_paths("test_dir/jcr_root/content/folder/.content.xml", "/content/dam/thumbnail_only")

    def test_asset_with_folder_thumbnail_paths_cleanup(self):
        """Test actual cleanup of folderThumbnailPaths references."""
        with self.runner.isolated_filesystem():
            # Create test structure
            os.makedirs("test_dir/jcr_root/content/dam/to_clean")
            os.makedirs("test_dir/jcr_root/content/folder")
            
            # Create a DAM asset
            with open("test_dir/jcr_root/content/dam/to_clean/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="dam:Asset">
    <jcr:content
        jcr:primaryType="dam:AssetContent">
        <metadata
            dam:MIMEtype="image/png"
            jcr:primaryType="nt:unstructured">
        </metadata>
    </jcr:content>
</jcr:root>""")

            # Create a folder that references the asset in folderThumbnailPaths
            with open("test_dir/jcr_root/content/folder/.content.xml", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:dam="http://www.day.com/dam/1.0" xmlns:nt="http://www.jcp.org/jcr/nt/1.0"
    jcr:primaryType="nt:file">
    <jcr:content
        dam:folderThumbnailPaths="[/content/dam/to_clean,/content/dam/other,/content/dam/another]"
        jcr:primaryType="nt:unstructured"/>
</jcr:root>""")

            # Test actual cleanup with confirmation
            result = self.runner.invoke(asset_remove_unused, ["test_dir"], input='y\n')

            assert result.exit_code == 0
            assert "CLEANED: /content/dam/to_clean (MIME: image/png) - removed from 1 folderThumbnailPaths" in result.output
            assert "folderThumbnailPaths references have been cleaned up" in result.output
            
            # Verify the reference was cleaned up
            assert not check_folder_thumbnail_paths("test_dir/jcr_root/content/folder/.content.xml", "/content/dam/to_clean")
            
            # Verify other references remain
            assert check_folder_thumbnail_paths("test_dir/jcr_root/content/folder/.content.xml", "/content/dam/other")
            assert check_folder_thumbnail_paths("test_dir/jcr_root/content/folder/.content.xml", "/content/dam/another")
            
            # Verify asset folder was deleted
            assert not Path("test_dir/jcr_root/content/dam/to_clean").exists() 