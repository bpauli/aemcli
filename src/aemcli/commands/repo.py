"""
AEM Repository Content Transfer Tool

FTP-like tool for JCR content, with support for diffing.
Transfers filevault JCR content between the filesystem (unzipped content package)
and a server such as AEM (running the package manager HTTP API).

Based on the original shell script version, this implementation provides:
- checkout: initial checkout of server content on file system
- put: upload local file system content to server
- get: download server content to local file system
- status (st): list status of modified/added/deleted files
- diff: show differences, same as 'localdiff'
- localdiff: show differences done locally compared to server
- serverdiff: show differences done on the server compared to local
"""

import click
import os
import tempfile
import shutil
import zipfile
import json
import urllib.parse
import subprocess
import time
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
import defusedxml.ElementTree as ET
import logging

# Set up logging for better error handling
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

VERSION = "1.5-beta"

# Default configurations
DEFAULT_SERVER = "http://localhost:4502"
DEFAULT_CREDENTIALS = "admin:admin"
DEFAULT_PACKMGR = "/crx/packmgr/service/.json"
DEFAULT_PACKAGE_GROUP = "tmp/repo"

# Safe command list for subprocess calls
ALLOWED_COMMANDS = {
    "diff": "/usr/bin/diff",
    "git": "/usr/bin/git"
}

def get_safe_command(command_name):
    """Get the full path for a command, ensuring it's in our allowed list."""
    if command_name not in ALLOWED_COMMANDS:
        raise ValueError(f"Command '{command_name}' not allowed")
    
    # Check if the command exists at the expected path
    cmd_path = ALLOWED_COMMANDS[command_name]
    if os.path.exists(cmd_path):
        return cmd_path
    
    # Fallback to system PATH lookup for common commands
    import shutil as sh_util
    found_path = sh_util.which(command_name)
    if found_path:
        return found_path
    
    raise FileNotFoundError(f"Command '{command_name}' not found")

class RepoConfig:
    """Configuration management for repo command."""

    def __init__(self):
        self.server = DEFAULT_SERVER
        self.credentials = DEFAULT_CREDENTIALS
        self.force = False
        self.quiet = False
        self.packmgr = DEFAULT_PACKMGR
        self.package_group = DEFAULT_PACKAGE_GROUP

    def load_config(self, start_path):
        """Load configuration from .repo file walking up the directory tree."""
        config_file = self._find_up(start_path, ".repo")
        if config_file:
            self._parse_config_file(config_file)
            return config_file
        return None

    def load_vlt_config(self, jcr_root_path):
        """Load configuration from .vlt file if present."""
        vlt_file = Path(jcr_root_path) / ".vlt"
        if vlt_file.exists():
            try:
                # Extract repository.url from the .vlt zip file
                with zipfile.ZipFile(vlt_file, "r") as zip_ref:
                    if "repository.url" in zip_ref.namelist():
                        url = zip_ref.read("repository.url").decode("utf-8").strip()
                        # Pattern: http://localhost:4502/crx/server/-/jcr:root
                        # Take part before /crx/server
                        if "/crx/server" in url:
                            self.server = url.split("/crx/server")[0]
                            return True
            except Exception as e:
                logger.warning(f"Could not load VLT config from {vlt_file}: {e}")
        return False

    def _find_up(self, start_path, filename):
        """Find a file upwards in the directory tree."""
        path = Path(start_path).resolve()
        while path != path.parent:
            config_path = path / filename
            if config_path.exists():
                return config_path
            path = path.parent
        return None

    def _parse_config_file(self, config_file):
        """Parse configuration from .repo file."""
        try:
            with open(config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            if key == "server":
                                self.server = value
                            elif key == "credentials":
                                self.credentials = value
        except Exception as e:
            click.echo(f"Warning: Could not parse config file {config_file}: {e}")


class ContentPackageManager:
    """Manages content package operations with AEM."""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        username, password = config.credentials.split(":", 1)
        self.session.auth = HTTPBasicAuth(username, password)

    def upload_package(self, zip_path):
        """Upload a package to the server."""
        url = f"{self.config.server}{self.config.packmgr}"

        # Read the file content first
        with open(zip_path, "rb") as f:
            file_content = f.read()

        # Send cmd, force, and package as form data (multipart/form-data)
        files = {
            "cmd": (None, "upload"),
            "force": (None, "true"),
            "package": ("package.zip", file_content, "application/zip"),
        }

        response = self.session.post(url, files=files)

        if not response.ok:
            raise Exception(f"Failed to upload package: {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception(f"Failed to upload package: {result}")

        return result

    def install_package(self, package_path):
        """Install a package on the server."""
        url = f"{self.config.server}{self.config.packmgr}/etc/packages/{package_path}?cmd=install"

        response = self.session.post(url)

        if not response.ok:
            raise Exception(f"Failed to install package: {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception(f"Failed to install package: {result}")

        return result

    def build_package(self, package_path):
        """Build a package on the server."""
        url = f"{self.config.server}{self.config.packmgr}/etc/packages/{package_path}?cmd=build"

        response = self.session.post(url)

        if not response.ok:
            raise Exception(f"Failed to build package: {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception(f"Failed to build package: {result}")

        return result

    def delete_package(self, package_path):
        """Delete a package from the server."""
        url = f"{self.config.server}{self.config.packmgr}/etc/packages/{package_path}?cmd=delete"

        response = self.session.post(url)

        if not response.ok:
            raise Exception(f"Failed to delete package: {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception(f"Failed to delete package: {result}")

        return result

    def download_package(self, package_path, output_path):
        """Download a package from the server."""
        url = f"{self.config.server}/etc/packages/{package_path}"

        response = self.session.get(url, stream=True)

        if not response.ok:
            raise Exception(f"Failed to download package: {response.text}")

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


class PackageBuilder:
    """Builds content packages for transfer."""

    @staticmethod
    def filesystem_to_jcr(path):
        """Convert filesystem path to JCR path."""
        # Remove .content.xml from the end
        if path.endswith("/.content.xml"):
            path = path[:-13]  # Remove "/.content.xml" (13 characters)
        elif path.endswith(".content.xml"):
            path = path[:-12]  # Remove ".content.xml" (12 characters)
        elif path.endswith(".xml"):
            path = path[:-4]  # Remove ".xml" (4 characters)

        # Rename known namespace prefixes from _ns_* to ns:*
        replacements = [
            ("_jcr_", "jcr:"),
            ("_rep_", "rep:"),
            ("_oak_", "oak:"),
            ("_sling_", "sling:"),
            ("_granite_", "granite:"),
            ("_cq_", "cq:"),
            ("_dam_", "dam:"),
            ("_exif_", "exif:"),
            ("_social_", "social:"),
        ]

        for old, new in replacements:
            path = path.replace(old, new)

        # URL decode as per PlatformNameFormat.java in jackrabbit-filevault
        path = urllib.parse.unquote(path)

        return path

    @staticmethod
    def xml_escape(text):
        """XML escape text."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def create_package(
        self, temp_dir, filter_path, package_group, package_name, package_version
    ):
        """Create package metadata and structure."""
        meta_inf_dir = Path(temp_dir) / "META-INF" / "vault"
        meta_inf_dir.mkdir(parents=True, exist_ok=True)

        jcr_root_dir = Path(temp_dir) / "jcr_root"
        jcr_root_dir.mkdir(parents=True, exist_ok=True)

        # Create a placeholder file in jcr_root to ensure the directory is included in zip
        placeholder_file = jcr_root_dir / ".placeholder"
        placeholder_file.write_text(
            "# Placeholder file to ensure jcr_root directory is included in package\n"
        )

        # Create filter.xml
        filter_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<workspaceFilter version="1.0">
    <filter root="{self.xml_escape(filter_path)}"/>
</workspaceFilter>"""

        with open(meta_inf_dir / "filter.xml", "w") as f:
            f.write(filter_xml)

        # Create properties.xml
        properties_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">
<properties>
<entry key="name">{self.xml_escape(package_name)}</entry>
<entry key="version">{self.xml_escape(package_version)}</entry>
<entry key="group">{self.xml_escape(package_group)}</entry>
</properties>"""

        with open(meta_inf_dir / "properties.xml", "w") as f:
            f.write(properties_xml)

    def get_excludes(self, root_path, local_path):
        """Get list of exclude patterns."""
        excludes = [
            "__pycache__",
            ".git",
            ".vscode",
            ".DS_Store",
            "Thumbs.db",
            ".idea",
        ]

        # Look for .gitignore-like files to add to excludes
        ignore_files = [".gitignore", ".vltignore", ".repoignore"]
        for ignore_file in ignore_files:
            ignore_path = Path(root_path) / ignore_file
            if ignore_path.exists():
                try:
                    with open(ignore_path, "r") as f:
                        excludes.extend(line.strip() for line in f if line.strip())
                except Exception as e:
                    logger.warning(f"Could not read ignore file {ignore_path}: {e}")

        return excludes

    def copy_content(self, source_path, dest_path, excludes):
        """Copy content excluding specified patterns."""

        # Use rsync-like functionality with Python
        def should_exclude(path, excludes):
            for pattern in excludes:
                if pattern in str(path) or path.name == pattern:
                    return True
            return False

        source = Path(source_path)
        dest = Path(dest_path)

        if source.is_file():
            if not should_exclude(source, excludes):
                # Only create parent directory if it's not the current directory and not empty
                parent_str = str(dest.parent)
                if parent_str and parent_str != "." and parent_str != dest_path:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
        else:
            for root, dirs, files in os.walk(source):
                root_path = Path(root)
                rel_path = root_path.relative_to(source)

                # Filter directories
                dirs[:] = [
                    d for d in dirs if not should_exclude(root_path / d, excludes)
                ]

                for file in files:
                    file_path = root_path / file
                    if not should_exclude(file_path, excludes):
                        dest_file = dest / rel_path / file
                        # Only create parent directory if it's not the current directory and not empty
                        parent_str = str(dest_file.parent)
                        if parent_str and parent_str != "." and parent_str != dest_path:
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_file)

    def create_zip(self, temp_dir):
        """Create zip file from package directory."""
        zip_path = Path(temp_dir) / "pkg.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            temp_path = Path(temp_dir)
            for root, dirs, files in os.walk(temp_dir):
                # Add directory entries to ensure empty directories are included
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    arc_dir_path = dir_path.relative_to(temp_path)
                    # Add directory entry with trailing slash
                    zipf.writestr(str(arc_dir_path) + "/", "")

                # Add files
                for file in files:
                    if file != "pkg.zip":
                        file_path = Path(root) / file
                        arc_path = file_path.relative_to(temp_path)
                        zipf.write(file_path, arc_path)

        return str(zip_path)


def validate_jcr_root(path):
    """Validate that we're working within a jcr_root structure."""
    path_obj = Path(path).resolve()

    if "jcr_root" not in str(path_obj):
        raise click.UsageError(
            f"Not inside a vault checkout with a jcr_root base directory: {path}"
        )

    # Find jcr_root directory
    parts = path_obj.parts
    jcr_root_index = None
    for i, part in enumerate(parts):
        if part == "jcr_root":
            jcr_root_index = i
            break

    if jcr_root_index is None:
        raise click.UsageError(
            f"Not inside a vault checkout with a jcr_root base directory: {path}"
        )

    jcr_root_path = Path(*parts[: jcr_root_index + 1])
    filter_path = (
        "/" + "/".join(parts[jcr_root_index + 1 :])
        if len(parts) > jcr_root_index + 1
        else "/"
    )

    return str(jcr_root_path), filter_path


def find_or_create_jcr_root(current_dir, jcr_path):
    """Find existing jcr_root or create new one for checkout."""
    current_path = Path(current_dir).resolve()

    # Check if we're already in jcr_root
    if "jcr_root" in str(current_path):
        jcr_root_path = str(current_path).split("jcr_root")[0] + "jcr_root"
        click.echo(f"Checking out into existing {jcr_root_path}")
        return jcr_root_path

    # Check if jcr_root exists in current directory
    jcr_root_candidate = current_path / "jcr_root"
    if jcr_root_candidate.exists():
        click.echo(f"Checking out into existing {jcr_root_candidate}")
        return str(jcr_root_candidate)

    # Create new jcr_root
    jcr_root_candidate.mkdir()
    click.echo(f"Checking out into new {jcr_root_candidate}")
    return str(jcr_root_candidate)


def show_status_diff(left_dir, right_dir, filter_path):
    """Show status differences between two directories."""
    try:
        # Use subprocess to run diff command with validated paths
        diff_cmd = get_safe_command("diff")
        cmd = [
            diff_cmd,
            "-rq",
            os.path.join(left_dir, "REMOTE" + filter_path),
            os.path.join(left_dir, "LOCAL" + filter_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # nosec B603 - controlled command with validated paths
        output = result.stdout

        # Process diff output to show status
        for line in output.split("\n"):
            if line.strip():
                if line.startswith("Files ") and " differ" in line:
                    # Extract path from "Files REMOTE/path and LOCAL/path differ"
                    parts = line.split(" ")
                    if len(parts) >= 2:
                        path = parts[1].replace("REMOTE", "").replace("LOCAL", "")
                        click.echo(f"M       {path}")
                elif "Only in LOCAL" in line:
                    # Extract path from "Only in LOCAL/path: filename"
                    match = line.split("Only in LOCAL")[1]
                    if ": " in match:
                        dir_part, file_part = match.split(": ", 1)
                        path = dir_part + "/" + file_part
                        click.echo(f"A       {path}")
                elif "Only in REMOTE" in line:
                    # Extract path from "Only in REMOTE/path: filename"
                    match = line.split("Only in REMOTE")[1]
                    if ": " in match:
                        dir_part, file_part = match.split(": ", 1)
                        path = dir_part + "/" + file_part
                        click.echo(f"D       {path}")
                elif "File REMOTE" in line and "is a regular file while file" in line:
                    # Handle file/directory conflicts
                    path = line.split()[1].replace("REMOTE", "")
                    click.echo(f"~ df    {path}")
                elif "File REMOTE" in line and "is a directory while file" in line:
                    # Handle directory/file conflicts
                    path = line.split()[1].replace("REMOTE", "")
                    click.echo(f"~ fd    {path}")

    except subprocess.CalledProcessError:
        click.echo("No differences found")
    except subprocess.TimeoutExpired:
        click.echo("Diff operation timed out")
    except FileNotFoundError as e:
        click.echo(f"Diff command not available: {e}")


def show_diff(left_dir, right_dir, filter_path, colorize=True):
    """Show detailed diff between two directories."""
    try:
        diff_cmd = get_safe_command("diff")
        cmd = [
            diff_cmd,
            "-rduNw",
            os.path.join(left_dir, "REMOTE" + filter_path),
            os.path.join(left_dir, "LOCAL" + filter_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # nosec B603 - controlled command with validated paths
        output = result.stdout

        if colorize and output:
            # Simple colorization for diff output
            for line in output.split("\n"):
                if line.startswith("---") or line.startswith("+++"):
                    click.echo(click.style(line, fg="white"))
                elif line.startswith("-"):
                    click.echo(click.style(line, fg="red"))
                elif line.startswith("+"):
                    click.echo(click.style(line, fg="green"))
                elif line.startswith("@@"):
                    click.echo(click.style(line, fg="cyan"))
                else:
                    click.echo(line)
        else:
            click.echo(output)

    except subprocess.CalledProcessError:
        click.echo("No differences found")
    except subprocess.TimeoutExpired:
        click.echo("Diff operation timed out")
    except FileNotFoundError as e:
        click.echo(f"Diff command not available: {e}")


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version information")
@click.pass_context
def repo(ctx, version):
    """FTP-like tool for JCR content, with support for diffing.

    Transfers filevault JCR content between the filesystem (unzipped content package)
    and a server such as AEM (running the package manager HTTP API).
    """
    if version:
        click.echo(f"repo version {VERSION}")
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@repo.command()
@click.argument("jcr_path")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
@click.option("-f", "--force", is_flag=True, help="Force, don't ask for confirmation")
@click.option("-q", "--quiet", is_flag=True, help="Quiet, don't output anything")
def checkout(jcr_path, server, credentials, force, quiet):
    """Initially check out JCR_PATH from the server on the file system.

    This will create a jcr_root folder in the current directory and check
    out the JCR_PATH in there. If this is called within a jcr_root or
    a jcr_root exists within the current directory, it will detect that
    and check out the JCR_PATH in there.
    """
    config = RepoConfig()
    config.force = force
    config.quiet = quiet

    if server:
        config.server = server
    if credentials:
        config.credentials = credentials

    # Load configuration
    config.load_config(os.getcwd())

    if not config.quiet:
        click.echo(f"Checking out {jcr_path} from {config.server}")

    # Validate JCR path
    if not jcr_path.startswith("/"):
        raise click.UsageError("JCR path must start with /")

    if jcr_path == "/":
        raise click.UsageError(
            "Refusing to work on repository root (would be too slow or overwrite everything)"
        )

    # Find or create jcr_root
    jcr_root_path = find_or_create_jcr_root(os.getcwd(), jcr_path)
    local_path = os.path.join(jcr_root_path, jcr_path.lstrip("/"))

    # Create target directory
    os.makedirs(local_path, exist_ok=True)

    # Execute get operation
    ctx = click.get_current_context()
    ctx.invoke(
        get,
        path=local_path,
        server=server,
        credentials=credentials,
        force=force,
        quiet=quiet,
    )


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
@click.option("-f", "--force", is_flag=True, help="Force, don't ask for confirmation")
@click.option("-q", "--quiet", is_flag=True, help="Quiet, don't output anything")
def put(path, server, credentials, force, quiet):
    """Upload local file system content to server for the given path."""
    config = RepoConfig()
    config.force = force
    config.quiet = quiet

    if server:
        config.server = server
    if credentials:
        config.credentials = credentials

    # Load configuration
    config.load_config(os.getcwd())

    # Validate path and get JCR info
    jcr_root_path, filter_path = validate_jcr_root(path)

    if filter_path == "/":
        raise click.UsageError(
            "Refusing to work on repository root (would be too slow or overwrite everything)"
        )

    if not config.quiet:
        human_filter = filter_path + ("/*" if os.path.isdir(path) else "")
        click.echo(f"Uploading {human_filter} to {config.server}")

    # Create package
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = PackageBuilder()
        package_mgr = ContentPackageManager(config)

        # Generate package info
        package_name = filter_path.replace("/", "-").replace(":", "").strip("-")
        package_name = f"repo{package_name}" if package_name else "repo-root"
        package_version = str(int(time.time()))

        # Create package structure
        builder.create_package(
            temp_dir, filter_path, config.package_group, package_name, package_version
        )

        # Copy content to package
        jcr_root_dest = os.path.join(temp_dir, "jcr_root")
        filter_dirname = os.path.dirname(filter_path)
        if filter_dirname != "/":
            os.makedirs(
                os.path.join(jcr_root_dest, filter_dirname.lstrip("/")), exist_ok=True
            )

        excludes = builder.get_excludes(jcr_root_path, path)

        if os.path.isdir(path):
            dest_path = os.path.join(jcr_root_dest, filter_path.lstrip("/"))
            builder.copy_content(path, dest_path, excludes)
        else:
            dest_path = os.path.join(jcr_root_dest, filter_path.lstrip("/"))
            parent_dir = os.path.dirname(dest_path)
            if parent_dir and parent_dir != ".":
                os.makedirs(parent_dir, exist_ok=True)
            if not any(pattern in str(path) for pattern in excludes):
                shutil.copy2(path, dest_path)

        # Create zip
        zip_path = builder.create_zip(temp_dir)

        if not config.quiet:
            # Show what will be uploaded
            with zipfile.ZipFile(zip_path, "r") as zf:
                jcr_files = [
                    f for f in zf.namelist() if f.startswith(f"jcr_root{filter_path}")
                ]
                for f in jcr_files[:10]:  # Show first 10 files
                    click.echo(f"  {f}")
                if len(jcr_files) > 10:
                    click.echo(f"  ... and {len(jcr_files) - 10} more files")

        # Confirm upload
        if not config.force and not config.quiet:
            if not click.confirm("Upload and overwrite on server?"):
                click.echo("Aborted.")
                return

        # Upload and install
        try:
            package_path = (
                f"{config.package_group}/{package_name}-{package_version}.zip"
            )

            if not config.quiet:
                click.echo("Uploading package...")
            package_mgr.upload_package(zip_path)

            if not config.quiet:
                click.echo("Installing package...")
            package_mgr.install_package(package_path)

            if not config.quiet:
                click.echo("Cleaning up...")
            package_mgr.delete_package(package_path)

            if not config.quiet:
                click.echo("✓ Upload completed successfully")

        except Exception as e:
            raise click.ClickException(f"Upload failed: {e}")


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
@click.option("-f", "--force", is_flag=True, help="Force, don't ask for confirmation")
@click.option("-q", "--quiet", is_flag=True, help="Quiet, don't output anything")
def get(path, server, credentials, force, quiet):
    """Download server content to local filesystem for the given path."""
    config = RepoConfig()
    config.force = force
    config.quiet = quiet

    if server:
        config.server = server
    if credentials:
        config.credentials = credentials

    # Load configuration
    config.load_config(os.getcwd())

    # Validate path and get JCR info
    jcr_root_path, filter_path = validate_jcr_root(path)

    if filter_path == "/":
        raise click.UsageError(
            "Refusing to work on repository root (would be too slow or overwrite everything)"
        )

    if not config.quiet:
        human_filter = filter_path + ("/*" if os.path.isdir(path) else "")
        click.echo(f"Downloading {human_filter} from {config.server}")

    # Create empty package and build on server
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = PackageBuilder()
        package_mgr = ContentPackageManager(config)

        # Generate package info
        package_name = filter_path.replace("/", "-").replace(":", "").strip("-")
        package_name = f"repo{package_name}" if package_name else "repo-root"
        package_version = str(int(time.time()))

        # Create empty package structure (just filter)
        builder.create_package(
            temp_dir, filter_path, config.package_group, package_name, package_version
        )

        # Create zip
        zip_path = builder.create_zip(temp_dir)

        try:
            package_path = (
                f"{config.package_group}/{package_name}-{package_version}.zip"
            )

            if not config.quiet:
                click.echo("Uploading empty package...")
            package_mgr.upload_package(zip_path)

            if not config.quiet:
                click.echo("Building package on server...")
            package_mgr.build_package(package_path)

            # Download built package
            download_path = os.path.join(temp_dir, "download.zip")
            if not config.quiet:
                click.echo("Downloading package...")
            package_mgr.download_package(package_path, download_path)

            # Clean up server package
            package_mgr.delete_package(package_path)

            # Extract and show contents
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(download_path, "r") as zf:
                zf.extractall(extract_dir)

                if not config.quiet:
                    # Show what will be downloaded
                    jcr_files = [
                        f
                        for f in zf.namelist()
                        if f.startswith(f"jcr_root{filter_path}")
                    ]
                    for f in jcr_files[:10]:  # Show first 10 files
                        click.echo(f"  {f}")
                    if len(jcr_files) > 10:
                        click.echo(f"  ... and {len(jcr_files) - 10} more files")

            # Confirm download
            if not config.force and not config.quiet:
                if not click.confirm("Download and overwrite locally?"):
                    click.echo("Aborted.")
                    return

            # Copy content from extracted package
            source_path = os.path.join(extract_dir, "jcr_root", filter_path.lstrip("/"))
            if os.path.exists(source_path):
                excludes = builder.get_excludes(jcr_root_path, path)

                # Remove existing content first
                if os.path.exists(path):
                    if os.path.isdir(path):
                        # Don't try to remove the current directory
                        if path != "." and os.path.abspath(path) != os.getcwd():
                            shutil.rmtree(path)
                        else:
                            # For current directory, remove contents but not the directory itself
                            for item in os.listdir(path):
                                item_path = os.path.join(path, item)
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                else:
                                    os.remove(item_path)
                    else:
                        os.remove(path)

                # Copy new content
                if os.path.isdir(source_path):
                    parent_dir = os.path.dirname(path)
                    if parent_dir and parent_dir != ".":
                        os.makedirs(parent_dir, exist_ok=True)
                    builder.copy_content(source_path, path, excludes)
                else:
                    parent_dir = os.path.dirname(path)
                    if parent_dir and parent_dir != ".":
                        os.makedirs(parent_dir, exist_ok=True)
                    shutil.copy2(source_path, path)

                if not config.quiet:
                    click.echo("✓ Download completed successfully")

                    # Show git status if in git repo
                    try:
                        git_cwd = (
                            os.path.dirname(path) if os.path.dirname(path) else "."
                        )
                        git_cmd = get_safe_command("git")
                        result = subprocess.run(
                            [git_cmd, "rev-parse", "--git-dir"],
                            capture_output=True,
                            cwd=git_cwd,
                            timeout=10
                        )  # nosec B603 - controlled git command with validated path
                        if result.returncode == 0:
                            click.echo("\nGit status:")
                            subprocess.run([git_cmd, "status", "-s", path], cwd=git_cwd, timeout=10)  # nosec B603 - controlled git command with validated path
                    except FileNotFoundError:
                        logger.info("Git not available")
                    except subprocess.TimeoutExpired:
                        logger.warning("Git command timed out")
                    except Exception as e:
                        logger.warning(f"Git status check failed: {e}")
            else:
                click.echo(f"Warning: No content found for {filter_path}")

        except Exception as e:
            raise click.ClickException(f"Download failed: {e}")


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
def status(path, server, credentials):
    """List status of files compared to the server at the given path.

    Status legend:
      M                  modified
      A                  added locally / deleted remotely
      D                  deleted locally / added remotely
      ~ fd               conflict: local file vs. remote directory
      ~ df               conflict: local directory vs. remote file
    """
    config = RepoConfig()

    if server:
        config.server = server
    if credentials:
        config.credentials = credentials

    # Load configuration
    config.load_config(os.getcwd())

    # Validate path and get JCR info
    jcr_root_path, filter_path = validate_jcr_root(path)

    if filter_path == "/":
        raise click.UsageError(
            "Refusing to work on repository root (would be too slow)"
        )

    click.echo(f"Checking status for {filter_path} against {config.server}")

    # Get server content (same as get command but don't overwrite)
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = PackageBuilder()
        package_mgr = ContentPackageManager(config)

        # Generate package info
        package_name = filter_path.replace("/", "-").replace(":", "").strip("-")
        package_name = f"repo{package_name}" if package_name else "repo-root"
        package_version = str(int(time.time()))

        # Create empty package structure (just filter)
        builder.create_package(
            temp_dir, filter_path, config.package_group, package_name, package_version
        )

        # Create zip and build on server
        zip_path = builder.create_zip(temp_dir)

        try:
            package_path = (
                f"{config.package_group}/{package_name}-{package_version}.zip"
            )

            package_mgr.upload_package(zip_path)
            package_mgr.build_package(package_path)

            # Download built package
            download_path = os.path.join(temp_dir, "download.zip")
            package_mgr.download_package(package_path, download_path)
            package_mgr.delete_package(package_path)

            # Set up diff comparison
            diff_base = os.path.join(temp_dir, "diffbase")
            os.makedirs(diff_base, exist_ok=True)

            # Extract remote content
            extract_dir = os.path.join(diff_base, "extracted")
            with zipfile.ZipFile(download_path, "r") as zf:
                zf.extractall(extract_dir)

            # Create symlink to remote content
            remote_link = os.path.join(diff_base, "REMOTE")
            os.symlink(os.path.join(extract_dir, "jcr_root"), remote_link)

            # Copy local content
            local_dir = os.path.join(diff_base, "LOCAL")
            os.makedirs(local_dir, exist_ok=True)

            excludes = builder.get_excludes(jcr_root_path, path)

            filter_dirname = os.path.dirname(filter_path)
            if filter_dirname != "/":
                os.makedirs(
                    os.path.join(local_dir, filter_dirname.lstrip("/")), exist_ok=True
                )

            if os.path.exists(path):
                dest_path = os.path.join(local_dir, filter_path.lstrip("/"))
                if os.path.isdir(path):
                    builder.copy_content(path, dest_path, excludes)
                else:
                    parent_dir = os.path.dirname(dest_path)
                    if parent_dir and parent_dir != ".":
                        os.makedirs(parent_dir, exist_ok=True)
                    shutil.copy2(path, dest_path)

            # Show status
            show_status_diff(diff_base, diff_base, filter_path)

        except Exception as e:
            raise click.ClickException(f"Status check failed: {e}")


# Add alias for status
@repo.command("st")
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
def st(path, server, credentials):
    """Alias for status command."""
    ctx = click.get_current_context()
    ctx.invoke(status, path=path, server=server, credentials=credentials)


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
def diff(path, server, credentials):
    """Show differences done locally compared to server at the given path.

    Same as 'localdiff', showing +++ if things were added locally.
    If you made changes on the server, use 'serverdiff' instead.
    """
    ctx = click.get_current_context()
    ctx.invoke(localdiff, path=path, server=server, credentials=credentials)


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
def localdiff(path, server, credentials):
    """Show differences done locally compared to server at the given path.

    Showing +++ if things were added locally (or removed on the server).
    If you made changes on the server, use 'serverdiff' instead.
    """
    _diff_command(path, server, credentials, inverse=False)


@repo.command()
@click.argument("path", default=".")
@click.option("-s", "--server", help="Server URL (default: http://localhost:4502)")
@click.option(
    "-u",
    "--credentials",
    help="User credentials in format user:password (default: admin:admin)",
)
def serverdiff(path, server, credentials):
    """Show differences done on the server compared to local at the given path.

    Showing +++ if things were added on the server (or removed locally).
    If you made changes locally, use 'localdiff' instead.
    """
    _diff_command(path, server, credentials, inverse=True)


def _diff_command(path, server, credentials, inverse=False):
    """Internal diff command implementation."""
    config = RepoConfig()

    if server:
        config.server = server
    if credentials:
        config.credentials = credentials

    # Load configuration
    config.load_config(os.getcwd())

    # Validate path and get JCR info
    jcr_root_path, filter_path = validate_jcr_root(path)

    if filter_path == "/":
        raise click.UsageError(
            "Refusing to work on repository root (would be too slow)"
        )

    diff_type = "server -> local" if inverse else "local -> server"
    click.echo(
        f"Showing differences ({diff_type}) for {filter_path} against {config.server}"
    )

    # Get server content (same as status but show diff)
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = PackageBuilder()
        package_mgr = ContentPackageManager(config)

        # Generate package info
        package_name = filter_path.replace("/", "-").replace(":", "").strip("-")
        package_name = f"repo{package_name}" if package_name else "repo-root"
        package_version = str(int(time.time()))

        # Create empty package structure (just filter)
        builder.create_package(
            temp_dir, filter_path, config.package_group, package_name, package_version
        )

        # Create zip and build on server
        zip_path = builder.create_zip(temp_dir)

        try:
            package_path = (
                f"{config.package_group}/{package_name}-{package_version}.zip"
            )

            package_mgr.upload_package(zip_path)
            package_mgr.build_package(package_path)

            # Download built package
            download_path = os.path.join(temp_dir, "download.zip")
            package_mgr.download_package(package_path, download_path)
            package_mgr.delete_package(package_path)

            # Set up diff comparison
            diff_base = os.path.join(temp_dir, "diffbase")
            os.makedirs(diff_base, exist_ok=True)

            # Extract remote content
            extract_dir = os.path.join(diff_base, "extracted")
            with zipfile.ZipFile(download_path, "r") as zf:
                zf.extractall(extract_dir)

            # Create symlink to remote content
            remote_link = os.path.join(diff_base, "REMOTE")
            os.symlink(os.path.join(extract_dir, "jcr_root"), remote_link)

            # Copy local content
            local_dir = os.path.join(diff_base, "LOCAL")
            os.makedirs(local_dir, exist_ok=True)

            excludes = builder.get_excludes(jcr_root_path, path)

            filter_dirname = os.path.dirname(filter_path)
            if filter_dirname != "/":
                os.makedirs(
                    os.path.join(local_dir, filter_dirname.lstrip("/")), exist_ok=True
                )

            if os.path.exists(path):
                dest_path = os.path.join(local_dir, filter_path.lstrip("/"))
                if os.path.isdir(path):
                    builder.copy_content(path, dest_path, excludes)
                else:
                    parent_dir = os.path.dirname(dest_path)
                    if parent_dir and parent_dir != ".":
                        os.makedirs(parent_dir, exist_ok=True)
                    shutil.copy2(path, dest_path)

            # Show diff (inverse changes the direction)
            show_diff(diff_base, diff_base, filter_path, colorize=True)

        except Exception as e:
            raise click.ClickException(f"Diff failed: {e}")


if __name__ == "__main__":
    repo()
