import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from aemcli.commands.content_cleanup import content_cleanup, get_default_properties, clean_xml_file


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
        assert default_props == expected_props
    
    def test_content_cleanup_default_behavior(self):
        """Test content cleanup with default properties."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")
            
            result = self.runner.invoke(content_cleanup, ["test_content", "--dry-run"])
            
            assert result.exit_code == 0
            assert "Using default AEM properties for removal" in result.output
            assert "Found 3 .content.xml files" in result.output
            assert "DRY RUN MODE" in result.output
    
    def test_content_cleanup_custom_properties(self):
        """Test content cleanup with custom properties only."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")
            
            result = self.runner.invoke(content_cleanup, [
                "test_content", "--dry-run", "cq:customProperty"
            ])
            
            assert result.exit_code == 0
            assert "Including custom properties: cq:customProperty" in result.output
            assert "Properties to remove: cq:customProperty" in result.output
    
    def test_content_cleanup_default_plus_custom(self):
        """Test content cleanup with default and custom properties."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")
            
            result = self.runner.invoke(content_cleanup, [
                "test_content", "--dry-run", "--default", "cq:customProperty"
            ])
            
            assert result.exit_code == 0
            assert "Including default AEM properties" in result.output
            assert "Including custom properties: cq:customProperty" in result.output
            assert "cq:customProperty" in result.output
            assert "jcr:uuid" in result.output
    
    def test_content_cleanup_nonexistent_path(self):
        """Test content cleanup with non-existent path."""
        result = self.runner.invoke(content_cleanup, ["nonexistent_path"])
        
        assert result.exit_code == 2
        assert "Path 'nonexistent_path' does not exist" in result.output
    
    def test_content_cleanup_no_xml_files(self):
        """Test content cleanup when no .content.xml files are found."""
        with self.runner.isolated_filesystem():
            os.makedirs("empty_dir")
            
            result = self.runner.invoke(content_cleanup, ["empty_dir"])
            
            assert result.exit_code == 0
            assert "No .content.xml files found" in result.output
    
    def test_content_cleanup_actual_modification(self):
        """Test that content cleanup actually modifies files."""
        with self.runner.isolated_filesystem():
            # Copy test files to isolated filesystem
            shutil.copytree(self.test_data_dir, "test_content")
            
            # Run without dry-run to actually modify files
            result = self.runner.invoke(content_cleanup, ["test_content"])
            
            assert result.exit_code == 0
            assert "Using default AEM properties for removal" in result.output
            
            # Check that properties were actually removed
            root_xml = Path("test_content/.content.xml")
            content = root_xml.read_text()
            
            # These properties should be removed
            assert 'jcr:uuid=' not in content
            assert 'cq:lastModified=' not in content
            assert 'jcr:lastModified=' not in content
            assert 'cq:isDelivered=' not in content
            
            # These properties should remain
            assert 'jcr:primaryType=' in content
            assert 'sling:resourceType=' in content
            assert 'jcr:title=' in content
    
    def test_clean_xml_file_function(self):
        """Test the clean_xml_file function directly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:uuid="test-uuid"
    cq:lastModified="2023-01-01"
    jcr:title="Test">
</jcr:root>''')
            f.flush()
            
            try:
                # Test dry run
                result = clean_xml_file(Path(f.name), {'jcr:uuid', 'cq:lastModified'}, dry_run=True)
                assert result is True
                
                # Verify file wasn't modified in dry run
                content = Path(f.name).read_text()
                assert 'jcr:uuid=' in content
                assert 'cq:lastModified=' in content
                
                # Test actual modification
                result = clean_xml_file(Path(f.name), {'jcr:uuid', 'cq:lastModified'}, dry_run=False)
                assert result is True
                
                # Verify file was modified
                content = Path(f.name).read_text()
                assert 'jcr:uuid=' not in content
                assert 'cq:lastModified=' not in content
                assert 'jcr:title=' in content  # Should remain
                
            finally:
                os.unlink(f.name)
    
    def test_clean_xml_file_no_changes_needed(self):
        """Test clean_xml_file when no properties need to be removed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0"
    jcr:primaryType="cq:Page"
    jcr:title="Test">
</jcr:root>''')
            f.flush()
            
            try:
                result = clean_xml_file(Path(f.name), {'jcr:uuid', 'cq:lastModified'}, dry_run=False)
                assert result is False
                
            finally:
                os.unlink(f.name)
    
    def test_help_output(self):
        """Test that help output is properly formatted."""
        result = self.runner.invoke(content_cleanup, ["--help"])
        
        assert result.exit_code == 0
        assert "Clean .content.xml files by removing specified properties" in result.output
        assert "--dry-run" in result.output
        assert "--default" in result.output
        assert "Examples:" in result.output
