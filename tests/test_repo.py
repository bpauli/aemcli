import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from aemcli.commands.repo import (
    repo,
    RepoConfig,
    PackageBuilder,
    validate_jcr_root,
    find_or_create_jcr_root,
    VERSION,
)
import pytest


class TestRepoCommand:
    """Test suite for repo command."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()

    def test_repo_version(self):
        """Test repo version command."""
        result = self.runner.invoke(repo, ["--version"])
        assert result.exit_code == 0
        assert f"repo version {VERSION}" in result.output

    def test_repo_help(self):
        """Test repo help command."""
        result = self.runner.invoke(repo, ["--help"])
        assert result.exit_code == 0
        assert "FTP-like tool for JCR content" in result.output
        assert "checkout" in result.output
        assert "put" in result.output
        assert "get" in result.output
        assert "status" in result.output
        assert "diff" in result.output

    def test_repo_subcommand_help(self):
        """Test repo subcommand help."""
        result = self.runner.invoke(repo, ["checkout", "--help"])
        assert result.exit_code == 0
        assert "Initially check out JCR_PATH" in result.output

        result = self.runner.invoke(repo, ["put", "--help"])
        assert result.exit_code == 0
        assert "Upload local file system content" in result.output

        result = self.runner.invoke(repo, ["get", "--help"])
        assert result.exit_code == 0
        assert "Download server content" in result.output

        result = self.runner.invoke(repo, ["status", "--help"])
        assert result.exit_code == 0
        assert "List status of files" in result.output

    def test_repo_status_alias(self):
        """Test repo st alias for status."""
        result = self.runner.invoke(repo, ["st", "--help"])
        assert result.exit_code == 0
        assert "Alias for status command" in result.output


class TestRepoConfig:
    """Test suite for RepoConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RepoConfig()
        assert config.server == "http://localhost:4502"
        assert config.credentials == "admin:admin"
        assert config.force is False
        assert config.quiet is False
        assert config.packmgr == "/crx/packmgr/service/.json"
        assert config.package_group == "tmp/repo"

    def test_load_config_file(self):
        """Test loading configuration from .repo file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / ".repo"
            config_file.write_text(
                """
# Test config file
server=http://test-server:8080
credentials=testuser:testpass
"""
            )

            config = RepoConfig()
            result = config.load_config(temp_dir)

            # Use resolve() to handle symlinks consistently
            assert result.resolve() == config_file.resolve()
            assert config.server == "http://test-server:8080"
            assert config.credentials == "testuser:testpass"

    def test_load_config_file_not_found(self):
        """Test loading configuration when .repo file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = RepoConfig()
            result = config.load_config(temp_dir)

            assert result is None
            # Should keep default values
            assert config.server == "http://localhost:4502"
            assert config.credentials == "admin:admin"


class TestPackageBuilder:
    """Test suite for PackageBuilder class."""

    def test_filesystem_to_jcr(self):
        """Test filesystem to JCR path conversion."""
        builder = PackageBuilder()

        # Test basic path conversion
        assert builder.filesystem_to_jcr("/apps/project") == "/apps/project"

        # Test .content.xml removal
        assert (
            builder.filesystem_to_jcr("/apps/project/.content.xml") == "/apps/project"
        )

        # Test .xml removal
        assert (
            builder.filesystem_to_jcr("/apps/project/component.xml")
            == "/apps/project/component"
        )

        # Test namespace conversion
        assert builder.filesystem_to_jcr("/apps/_jcr_content") == "/apps/jcr:content"
        assert builder.filesystem_to_jcr("/apps/_cq_dialog") == "/apps/cq:dialog"
        assert (
            builder.filesystem_to_jcr("/apps/_sling_resourceType")
            == "/apps/sling:resourceType"
        )

    def test_xml_escape(self):
        """Test XML escaping functionality."""
        builder = PackageBuilder()

        assert builder.xml_escape("simple") == "simple"
        assert builder.xml_escape("test & value") == "test &amp; value"
        assert builder.xml_escape("test < value") == "test &lt; value"
        assert builder.xml_escape("test > value") == "test &gt; value"
        assert (
            builder.xml_escape('test "quoted" value') == "test &quot;quoted&quot; value"
        )
        assert (
            builder.xml_escape("test 'quoted' value") == "test &apos;quoted&apos; value"
        )

    def test_get_excludes(self):
        """Test getting exclude patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            builder = PackageBuilder()

            # Create test ignore files
            vltignore = Path(temp_dir) / ".vltignore"
            vltignore.write_text("*.tmp\n.cache/\n")

            repoignore = Path(temp_dir) / ".repoignore"
            repoignore.write_text("*.log\n.debug/\n")

            excludes = builder.get_excludes(temp_dir, temp_dir)

            # Should include default excludes
            assert ".repo" in excludes
            assert ".vlt" in excludes
            assert ".DS_Store" in excludes

            # Should include custom excludes from ignore files
            assert "*.tmp" in excludes
            assert ".cache/" in excludes
            assert "*.log" in excludes
            assert ".debug/" in excludes


class TestJcrRootValidation:
    """Test suite for JCR root validation functions."""

    def test_validate_jcr_root_valid_path(self):
        """Test validation of valid jcr_root paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create jcr_root structure
            jcr_root = Path(temp_dir) / "jcr_root"
            jcr_root.mkdir()

            apps_dir = jcr_root / "apps" / "project"
            apps_dir.mkdir(parents=True)

            # Test validation
            jcr_root_path, filter_path = validate_jcr_root(str(apps_dir))

            # Use resolve() to handle symlinks consistently
            assert Path(jcr_root_path).resolve() == jcr_root.resolve()
            assert filter_path == "/apps/project"

    def test_validate_jcr_root_invalid_path(self):
        """Test validation of invalid paths (not in jcr_root)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(Exception) as exc_info:
                validate_jcr_root(temp_dir)

            assert "Not inside a vault checkout" in str(exc_info.value)

    def test_find_or_create_jcr_root_existing(self):
        """Test finding existing jcr_root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing jcr_root
            jcr_root = Path(temp_dir) / "jcr_root"
            jcr_root.mkdir()

            result = find_or_create_jcr_root(temp_dir, "/apps/test")

            # Use resolve() to handle symlinks consistently
            assert Path(result).resolve() == jcr_root.resolve()
            assert jcr_root.exists()

    def test_find_or_create_jcr_root_new(self):
        """Test creating new jcr_root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = find_or_create_jcr_root(temp_dir, "/apps/test")

            expected_path = Path(temp_dir) / "jcr_root"
            # Use resolve() to handle symlinks consistently
            assert Path(result).resolve() == expected_path.resolve()
            assert expected_path.exists()


class TestRepoCommandValidation:
    """Test suite for repo command validation."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()

    def test_checkout_requires_jcr_path(self):
        """Test that checkout command requires a JCR path argument."""
        result = self.runner.invoke(repo, ["checkout"])
        assert result.exit_code == 2
        assert "Missing argument" in result.output

    def test_checkout_validates_jcr_path(self):
        """Test that checkout validates JCR path format."""
        result = self.runner.invoke(repo, ["checkout", "invalid-path"])
        assert result.exit_code == 2
        assert "JCR path must start with /" in result.output

    def test_checkout_rejects_root_path(self):
        """Test that checkout rejects repository root path."""
        result = self.runner.invoke(repo, ["checkout", "/"])
        assert result.exit_code == 2
        assert "Refusing to work on repository root" in result.output

    def test_put_requires_jcr_root_context(self):
        """Test that put command requires jcr_root context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            result = self.runner.invoke(repo, ["put"])
            assert result.exit_code == 2
            assert "Not inside a vault checkout" in result.output

    def test_get_requires_jcr_root_context(self):
        """Test that get command requires jcr_root context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            result = self.runner.invoke(repo, ["get"])
            assert result.exit_code == 2
            assert "Not inside a vault checkout" in result.output

    def test_status_requires_jcr_root_context(self):
        """Test that status command requires jcr_root context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            result = self.runner.invoke(repo, ["status"])
            assert result.exit_code == 2
            assert "Not inside a vault checkout" in result.output
