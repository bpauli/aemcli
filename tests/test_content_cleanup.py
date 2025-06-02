import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from aemcli.commands.content_cleanup import (
    content_cleanup,
    get_default_properties,
    clean_xml_file,
    determine_properties_to_remove,
    process_files_for_properties,
    print_summary,
    mangle_node_name,
    unmangle_node_name,
    remove_node_from_xml,
    find_node_folders,
    remove_node_folders,
    process_files_for_nodes,
)


class TestContentCleanup:
    """Test suite for content_cleanup command."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()
        self.test_data_dir = Path(__file__).parent / "test_content" / "content_cleanup"

    def test_get_default_properties(self):
        """Test that default properties are correctly defined."""
        default_props = get_default_properties()
        expected_props = {
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
        assert default_props == expected_props

    def test_mangle_unmangle_node_names(self):
        """Test node name mangling and unmangling."""
        # Test basic mangling
        assert mangle_node_name("jcr:content") == "_jcr_content"
        assert mangle_node_name("rep:policy") == "_rep_policy"
        assert mangle_node_name("simple") == "simple"
        
        # Test unmangling
        assert unmangle_node_name("_jcr_content") == "jcr:content"
        assert unmangle_node_name("_rep_policy") == "rep:policy"
        assert unmangle_node_name("simple") == "simple"
        assert unmangle_node_name("_simple") == "_simple"  # Not a mangled name

    def test_mangle_node_name_edge_cases(self):
        """Test node name mangling with edge cases."""
        # Empty string
        assert mangle_node_name("") == ""
        
        # Multiple colons
        assert mangle_node_name("ns1:ns2:name") == "_ns1_ns2_name"
        
        # Already starts with underscore
        assert mangle_node_name("_already:mangled") == "__already_mangled"
        
        # Only colon - results in underscore prefix plus underscore for colon replacement
        assert mangle_node_name(":") == "__"

    def test_unmangle_node_name_edge_cases(self):
        """Test node name unmangling with edge cases."""
        # Empty string
        assert unmangle_node_name("") == ""
        
        # Just underscore
        assert unmangle_node_name("_") == "_"
        
        # Multiple underscores at start - unmangles first underscore part
        assert unmangle_node_name("__test_something") == ":test_something"
        
        # No underscores after first
        assert unmangle_node_name("_nomore") == "_nomore"

    def test_remove_node_from_xml_self_closing(self):
        """Test removing self-closing nodes from XML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test Page">
    <jcr:content jcr:primaryType="cq:PageContent" />
    <cq:dialog jcr:primaryType="nt:unstructured" />
    <otherNode jcr:primaryType="nt:unstructured" />
</jcr:root>""")
            f.flush()

            try:
                # Test dry run
                result = remove_node_from_xml(Path(f.name), "jcr:content", dry_run=True)
                assert result is True

                # Verify file wasn't modified in dry run
                content = Path(f.name).read_text()
                assert "<jcr:content" in content

                # Test actual removal
                result = remove_node_from_xml(Path(f.name), "jcr:content", dry_run=False)
                assert result is True

                # Verify node was removed
                content = Path(f.name).read_text()
                assert "<jcr:content" not in content
                assert "<cq:dialog" in content  # Other nodes should remain
                assert "<otherNode" in content

            finally:
                os.unlink(f.name)

    def test_remove_node_from_xml_with_content(self):
        """Test removing nodes with content from XML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test Page">
    <jcr:content jcr:primaryType="cq:PageContent">
        <nested jcr:primaryType="nt:unstructured" />
    </jcr:content>
    <cq:dialog jcr:primaryType="nt:unstructured">
        <items jcr:primaryType="nt:unstructured" />
    </cq:dialog>
</jcr:root>""")
            f.flush()

            try:
                # Test removal of node with content
                result = remove_node_from_xml(Path(f.name), "jcr:content", dry_run=False)
                assert result is True

                # Verify node and its content were removed
                content = Path(f.name).read_text()
                assert "<jcr:content" not in content
                assert "</jcr:content>" not in content
                assert "<nested" not in content
                assert "<cq:dialog" in content  # Other nodes should remain

            finally:
                os.unlink(f.name)

    def test_remove_node_from_xml_nonexistent_node(self):
        """Test removing a node that doesn't exist."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test Page">
    <jcr:content jcr:primaryType="cq:PageContent" />
</jcr:root>""")
            f.flush()

            try:
                # Test removal of non-existent node
                result = remove_node_from_xml(Path(f.name), "nonexistent", dry_run=False)
                assert result is False

                # Verify file wasn't changed
                content = Path(f.name).read_text()
                assert "<jcr:content" in content

            finally:
                os.unlink(f.name)

    def test_remove_node_from_xml_special_characters(self):
        """Test removing nodes with special characters in names."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page">
    <node-with-dashes jcr:primaryType="nt:unstructured" />
    <node_with_underscores jcr:primaryType="nt:unstructured" />
    <node.with.dots jcr:primaryType="nt:unstructured" />
</jcr:root>""")
            f.flush()

            try:
                # Test removal of node with dashes
                result = remove_node_from_xml(Path(f.name), "node-with-dashes", dry_run=False)
                assert result is True

                content = Path(f.name).read_text()
                assert "node-with-dashes" not in content
                assert "node_with_underscores" in content
                assert "node.with.dots" in content

            finally:
                os.unlink(f.name)

    def test_remove_node_from_xml_file_error(self):
        """Test handling of file errors during node removal."""
        # Test with non-existent file
        result = remove_node_from_xml(Path("/nonexistent/file.xml"), "jcr:content", dry_run=False)
        assert result is False

    def test_find_node_folders(self):
        """Test finding folders with node names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create various folders
            (base_path / "jcr:content").mkdir()  # Original name
            (base_path / "_jcr_content").mkdir()  # Mangled name
            (base_path / "_rep_policy").mkdir()   # Another mangled name
            (base_path / "regular_folder").mkdir()  # Regular folder
            (base_path / "subfolder" / "_jcr_content").mkdir(parents=True)  # Nested mangled folder
            
            # Test finding jcr:content folders
            folders = find_node_folders(base_path, "jcr:content")
            folder_names = [f.name for f in folders]
            
            assert len(folders) == 3  # Should find original, mangled, and nested
            assert "jcr:content" in folder_names
            assert "_jcr_content" in folder_names
            assert any(f.name == "_jcr_content" and f.parent.name == "subfolder" for f in folders)

    def test_find_node_folders_no_matches(self):
        """Test finding folders when no matches exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create some folders that don't match
            (base_path / "regular_folder").mkdir()
            (base_path / "another_folder").mkdir()
            
            # Test finding non-existent node folders
            folders = find_node_folders(base_path, "jcr:content")
            assert len(folders) == 0

    def test_find_node_folders_empty_directory(self):
        """Test finding folders in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            folders = find_node_folders(base_path, "jcr:content")
            assert len(folders) == 0

    def test_remove_node_folders_dry_run(self):
        """Test removing node folders in dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create test folders
            folder1 = base_path / "_jcr_content"
            folder2 = base_path / "subfolder" / "_jcr_content"
            folder1.mkdir()
            folder2.mkdir(parents=True)
            
            # Create some files in folders to make sure they exist
            (folder1 / "test.txt").write_text("test")
            (folder2 / "test.txt").write_text("test")
            
            folders = [folder1, folder2]
            
            # Test dry run
            removed_count, total_count = remove_node_folders(folders, dry_run=True)
            
            assert removed_count == 2
            assert total_count == 2
            
            # Verify folders still exist
            assert folder1.exists()
            assert folder2.exists()

    def test_remove_node_folders_actual_removal(self):
        """Test actually removing node folders."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create test folders
            folder1 = base_path / "_jcr_content"
            folder2 = base_path / "subfolder" / "_jcr_content"
            folder1.mkdir()
            folder2.mkdir(parents=True)
            
            # Create some files in folders
            (folder1 / "test.txt").write_text("test")
            (folder2 / "test.txt").write_text("test")
            
            folders = [folder1, folder2]
            
            # Test actual removal
            removed_count, total_count = remove_node_folders(folders, dry_run=False)
            
            assert removed_count == 2
            assert total_count == 2
            
            # Verify folders are gone
            assert not folder1.exists()
            assert not folder2.exists()
            # But parent directories should still exist
            assert (base_path / "subfolder").exists()

    def test_remove_node_folders_permission_error(self):
        """Test handling permission errors during folder removal."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create a folder that we'll make read-only
            folder = base_path / "_jcr_content"
            folder.mkdir()
            
            # Create a read-only file inside to make removal fail
            readonly_file = folder / "readonly.txt"
            readonly_file.write_text("test")
            readonly_file.chmod(0o444)  # Read-only
            
            try:
                # Make the folder read-only too
                folder.chmod(0o444)
                
                folders = [folder]
                
                # Test removal with permission error
                removed_count, total_count = remove_node_folders(folders, dry_run=False)
                
                # Should handle the error gracefully
                assert removed_count == 0  # Failed to remove
                assert total_count == 1
                
            finally:
                # Clean up - restore permissions so temp dir can be deleted
                try:
                    folder.chmod(0o755)
                    readonly_file.chmod(0o644)
                except:
                    pass

    def test_remove_node_folders_empty_list(self):
        """Test removing node folders with empty list."""
        removed_count, total_count = remove_node_folders([], dry_run=False)
        
        assert removed_count == 0
        assert total_count == 0

    def test_process_files_for_nodes(self):
        """Test processing multiple files for node removal."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create test files
            file1 = base_path / "file1.xml"
            file2 = base_path / "file2.xml"
            file3 = base_path / "file3.xml"
            
            file1.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0">
    <jcr:content jcr:primaryType="cq:PageContent" />
</jcr:root>""")

            file2.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0">
    <jcr:content jcr:primaryType="cq:PageContent" />
    <otherNode jcr:primaryType="nt:unstructured" />
</jcr:root>""")

            file3.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0">
    <otherNode jcr:primaryType="nt:unstructured" />
</jcr:root>""")
            
            files = [file1, file2, file3]
            
            # Test processing files
            modified_count, total_count = process_files_for_nodes(files, "jcr:content", dry_run=False)
            
            assert modified_count == 2  # file1 and file2 should be modified
            assert total_count == 3
            
            # Verify modifications
            assert "jcr:content" not in file1.read_text()
            assert "jcr:content" not in file2.read_text()
            assert "otherNode" in file2.read_text()  # Should remain
            assert "jcr:content" not in file3.read_text()  # Wasn't there to begin with
            assert "otherNode" in file3.read_text()  # Should remain

    def test_content_cleanup_node_command(self):
        """Test content cleanup node command for removing nodes."""
        with self.runner.isolated_filesystem():
            # Create a test .content.xml file with a node to remove
            os.makedirs("test_content")
            test_file = Path("test_content/.content.xml")
            test_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test Page">
    <jcr:content jcr:primaryType="cq:PageContent" jcr:title="Content" />
    <otherNode jcr:primaryType="nt:unstructured" />
</jcr:root>""")

            # Create a folder that matches the mangled name
            os.makedirs("test_content/_jcr_content")

            result = self.runner.invoke(content_cleanup, ["node", "jcr:content", "test_content", "--dry-run"])

            assert result.exit_code == 0
            assert "Node to remove: jcr:content" in result.output
            assert "Mangled folder name: _jcr_content" in result.output
            assert "DRY RUN MODE" in result.output
            assert "Would clean:" in result.output
            assert "Would remove folder:" in result.output

    def test_content_cleanup_node_command_nonexistent_path(self):
        """Test node command with non-existent path."""
        result = self.runner.invoke(content_cleanup, ["node", "jcr:content", "nonexistent_path"])

        assert result.exit_code == 2
        assert "Path 'nonexistent_path' does not exist" in result.output

    def test_content_cleanup_node_command_no_files_or_folders(self):
        """Test node command when no files or folders are found."""
        with self.runner.isolated_filesystem():
            os.makedirs("empty_dir")

            result = self.runner.invoke(content_cleanup, ["node", "jcr:content", "empty_dir"])

            assert result.exit_code == 0
            assert "No .content.xml files found" in result.output
            assert "No folders found with name 'jcr:content' or '_jcr_content'" in result.output

    def test_content_cleanup_node_command_actual_removal(self):
        """Test that node command actually removes nodes and folders."""
        with self.runner.isolated_filesystem():
            # Create test structure
            os.makedirs("test_content/_jcr_content")
            test_file = Path("test_content/.content.xml")
            test_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page">
    <jcr:content jcr:primaryType="cq:PageContent" />
    <otherNode jcr:primaryType="nt:unstructured" />
</jcr:root>""")

            # Run actual removal
            result = self.runner.invoke(content_cleanup, ["node", "jcr:content", "test_content"])

            assert result.exit_code == 0
            
            # Verify node was removed from XML
            content = test_file.read_text()
            assert "jcr:content" not in content
            assert "otherNode" in content  # Should remain
            
            # Verify folder was removed
            assert not Path("test_content/_jcr_content").exists()

    def test_content_cleanup_property_default_behavior(self):
        """Test content cleanup property command with default properties."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")

            result = self.runner.invoke(content_cleanup, ["property", "test_content", "--dry-run"])

            assert result.exit_code == 0
            assert "Using default AEM properties for removal" in result.output
            assert "Found 3 .content.xml files" in result.output
            assert "DRY RUN MODE" in result.output

    def test_content_cleanup_property_custom_properties(self):
        """Test content cleanup property command with custom properties only."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")

            result = self.runner.invoke(
                content_cleanup, ["property", "test_content", "--dry-run", "cq:customProperty"]
            )

            assert result.exit_code == 0
            assert "Including custom properties: cq:customProperty" in result.output
            assert "Properties to remove: cq:customProperty" in result.output

    def test_content_cleanup_property_default_plus_custom(self):
        """Test content cleanup property command with default and custom properties."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")

            result = self.runner.invoke(
                content_cleanup,
                ["property", "test_content", "--dry-run", "--default", "cq:customProperty"],
            )

            assert result.exit_code == 0
            assert "Including default AEM properties" in result.output
            assert "Including custom properties: cq:customProperty" in result.output
            assert "cq:customProperty" in result.output
            assert "jcr:uuid" in result.output

    def test_content_cleanup_property_nonexistent_path(self):
        """Test content cleanup property command with non-existent path."""
        result = self.runner.invoke(content_cleanup, ["property", "nonexistent_path"])

        assert result.exit_code == 2
        assert "Path 'nonexistent_path' does not exist" in result.output

    def test_content_cleanup_property_no_xml_files(self):
        """Test content cleanup property command when no .content.xml files are found."""
        with self.runner.isolated_filesystem():
            os.makedirs("empty_dir")

            result = self.runner.invoke(content_cleanup, ["property", "empty_dir"])

            assert result.exit_code == 0
            assert "No .content.xml files found" in result.output

    def test_content_cleanup_property_actual_modification(self):
        """Test that content cleanup property command actually modifies files."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")

            # Run without dry-run to actually modify files
            result = self.runner.invoke(content_cleanup, ["property", "test_content"])

            assert result.exit_code == 0
            assert "Using default AEM properties for removal" in result.output

            # Check that properties were actually removed
            root_xml = Path("test_content/.content.xml")
            content = root_xml.read_text()

            # These properties should be removed
            assert "jcr:uuid=" not in content
            assert "cq:lastModified=" not in content
            assert "jcr:lastModified=" not in content
            assert "cq:isDelivered=" not in content
            # Check new _preview and _scene7 properties are removed
            assert "cq:lastReplicated_preview=" not in content
            assert "cq:lastReplicated_scene7=" not in content
            assert "cq:lastReplicatedBy_preview=" not in content
            assert "cq:lastReplicatedBy_scene7=" not in content
            assert "cq:lastReplicationAction_preview=" not in content
            assert "cq:lastReplicationAction_scene7=" not in content

            # These properties should remain
            assert "jcr:primaryType=" in content
            assert "sling:resourceType=" in content
            assert "jcr:title=" in content

            # Check subpage file as well
            subpage_xml = Path("test_content/subpage/.content.xml")
            subpage_content = subpage_xml.read_text()

            # These should be removed from subpage
            assert "jcr:uuid=" not in subpage_content
            assert "cq:lastReplicated_preview=" not in subpage_content
            assert "cq:lastReplicatedBy_scene7=" not in subpage_content
            assert "cq:lastReplicationAction_preview=" not in subpage_content

            # These should remain in subpage
            assert "cq:customProperty=" in subpage_content
            assert "sling:resourceType=" in subpage_content
            assert "jcr:title=" in subpage_content

    def test_clean_xml_file_function(self):
        """Test the clean_xml_file function directly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:uuid="test-uuid"
    cq:lastModified="2023-01-01"
    jcr:title="Test">
</jcr:root>"""
            )
            f.flush()

            try:
                # Test dry run
                result = clean_xml_file(
                    Path(f.name), {"jcr:uuid", "cq:lastModified"}, dry_run=True
                )
                assert result is True

                # Verify file wasn't modified in dry run
                content = Path(f.name).read_text()
                assert "jcr:uuid=" in content
                assert "cq:lastModified=" in content

                # Test actual modification
                result = clean_xml_file(
                    Path(f.name), {"jcr:uuid", "cq:lastModified"}, dry_run=False
                )
                assert result is True

                # Verify file was modified
                content = Path(f.name).read_text()
                assert "jcr:uuid=" not in content
                assert "cq:lastModified=" not in content
                assert "jcr:title=" in content  # Should remain

            finally:
                os.unlink(f.name)

    def test_clean_xml_file_no_changes_needed(self):
        """Test clean_xml_file when no properties need to be removed."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test">
</jcr:root>"""
            )
            f.flush()

            try:
                result = clean_xml_file(
                    Path(f.name), {"jcr:uuid", "cq:lastModified"}, dry_run=False
                )
                assert result is False

            finally:
                os.unlink(f.name)

    def test_help_output(self):
        """Test that help output is properly formatted."""
        result = self.runner.invoke(content_cleanup, ["--help"])

        assert result.exit_code == 0
        assert "Clean .content.xml files and remove nodes/folders" in result.output

        # Test property subcommand help
        result = self.runner.invoke(content_cleanup, ["property", "--help"])
        assert result.exit_code == 0
        assert "Clean .content.xml files by removing specified properties" in result.output
        assert "--dry-run" in result.output
        assert "--default" in result.output
        assert "Examples:" in result.output

        # Test node subcommand help
        result = self.runner.invoke(content_cleanup, ["node", "--help"])
        assert result.exit_code == 0
        assert "Remove nodes from .content.xml files and delete corresponding folders" in result.output
        # The text might be split across lines, so check for the key parts
        assert "Node name mangling" in result.output
        assert "handled" in result.output
        assert "automatically" in result.output
