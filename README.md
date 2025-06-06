# AEM CLI

[![Tests](https://github.com/bpauli/aemcli/workflows/Tests/badge.svg)](https://github.com/bpauli/aemcli/actions/workflows/test.yml)
[![CI](https://github.com/bpauli/aemcli/workflows/CI/badge.svg)](https://github.com/bpauli/aemcli/actions/workflows/ci.yml)

A command-line tool for Adobe Experience Manager (AEM) content management and cleanup operations.

## Overview

AEM CLI provides utilities for managing AEM content repositories, with a focus on cleaning and maintaining `.content.xml` files and transferring JCR content between filesystem and server. The tool helps developers and content managers automate common AEM maintenance tasks.

## Commands

- **[content-cleanup](#content-cleanup-command)** - Clean AEM metadata properties and remove nodes from `.content.xml` files
- **[asset-remove-unused](#asset-remove-unused-command)** - Find and remove unused DAM assets with reference checking
- **[repo](#repository-content-transfer-command)** - FTP-like tool for JCR content transfer between filesystem and server

## Features

### Content Cleanup
- **Remove AEM metadata properties** from `.content.xml` files
- **Remove nodes and folders** with automatic name mangling support
- **Flexible property selection** - use default AEM properties or specify custom ones
- **Recursive processing** - handles entire directory trees
- **Dry-run mode** - preview changes before applying them
- **Detailed reporting** - see exactly what properties and nodes are removed

#### Property Cleanup
The tool removes common AEM system properties that are typically not needed in source control:

- `cq:isDelivered`, `cq:lastModified`, `cq:lastModifiedBy`
- `cq:lastReplicated*`, `cq:lastReplicatedBy*`, `cq:lastReplicationAction*`
- `jcr:isCheckedOut`, `jcr:lastModified`, `jcr:lastModifiedBy`, `jcr:uuid`

#### Node Cleanup
- **Remove specific nodes** from all `.content.xml` files
- **Delete corresponding folders** with matching names
- **Automatic name mangling** - handles JCR to filesystem name conversion (e.g., `jcr:content` ↔ `_jcr_content`)
- **Safe removal** - preserves other nodes and content structure
- **Current directory default** - works from any directory without specifying paths

### Asset Cleanup
- **Find unused DAM assets** with common MIME types (images, videos, documents, audio)
- **Reference checking** - scans all `.content.xml` files for `image` and `fileReference` properties
- **Smart thumbnail cleanup** - handles `dam:folderThumbnailPaths` references properly
- **Confirmation prompts** - asks for confirmation before deletion with detailed summary
- **Dry-run mode** - preview what would be deleted without making changes
- **Comprehensive reporting** - shows used vs unused assets with reference counts

#### Supported Asset Types
The tool focuses on common MIME types that are typically managed in DAM:

- **Images**: JPEG, PNG, GIF, WebP, SVG, BMP, TIFF
- **Videos**: MP4, AVI, MOV, WMV, FLV, WebM, MKV
- **Documents**: PDF, Word, Excel, PowerPoint
- **Audio**: MP3, WAV, OGG, AAC, M4A

### Repository Content Transfer (repo)
- **FTP-like tool for JCR content** with support for diffing
- **Checkout** - initial checkout of server content to filesystem
- **Put** - upload local filesystem content to server
- **Get** - download server content to local filesystem
- **Status** - list status of modified/added/deleted files
- **Diff** - show differences between local and server content
- **Configuration support** - `.repo` files for server/credentials
- **Package-based transfers** - uses AEM package manager HTTP API

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install from Source
```bash
# Clone the repository
git clone <repository-url>
cd aemcli

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Usage

### Content Cleanup Command

The `content-cleanup` command has two subcommands for different types of cleanup operations:

#### Property Cleanup (content-cleanup property)

##### Basic Usage
```bash
# Clean using default AEM properties
aemcli content-cleanup property /path/to/content

# Preview changes without modifying files
aemcli content-cleanup property /path/to/content --dry-run
```

##### Advanced Usage
```bash
# Use only custom properties
aemcli content-cleanup property /path/to/content cq:customProp jcr:myProp

# Combine default and custom properties
aemcli content-cleanup property /path/to/content --default cq:customProp

# Explicitly use default properties
aemcli content-cleanup property /path/to/content --default
```

##### Options
- `--dry-run` - Show what would be changed without modifying files
- `--default` - Include default AEM properties in removal list
- `--help` - Show detailed help and examples

#### Node Cleanup (content-cleanup node)

##### Basic Usage
```bash
# Remove jcr:content nodes and folders from current directory
aemcli content-cleanup node jcr:content

# Preview changes without modifying files
aemcli content-cleanup node jcr:content --dry-run

# Remove nodes from specific path
aemcli content-cleanup node cq:dialog /path/to/content
```

##### Advanced Usage
```bash
# Remove different types of nodes
aemcli content-cleanup node rep:policy
aemcli content-cleanup node cq:EditConfig
aemcli content-cleanup node cq:childEditConfig

# Remove nodes with special characters
aemcli content-cleanup node "node-with-dashes"
aemcli content-cleanup node "node.with.dots"
```

##### How Node Cleanup Works
1. **Name Mangling**: Automatically handles JCR to filesystem name conversion
   - `jcr:content` → `_jcr_content`
   - `rep:policy` → `_rep_policy`
   - Regular names remain unchanged
2. **XML Processing**: Removes matching nodes from all `.content.xml` files
   - Handles both self-closing tags (`<nodeName />`) and tags with content
   - Preserves other nodes and XML structure
3. **Folder Removal**: Finds and removes folders with matching names (both original and mangled)
4. **Safety Features**: Dry-run mode and detailed reporting

##### Options
- `--dry-run` - Show what would be changed without modifying files
- `--help` - Show detailed help and examples

### Asset Remove Unused Command

#### Basic Usage
```bash
# Find and remove unused DAM assets (with confirmation)
aemcli asset-remove-unused /path/to/content/dam

# Preview what would be deleted without making changes
aemcli asset-remove-unused /path/to/content/dam --dry-run
```

#### Advanced Usage
```bash
# Start from specific directory
aemcli asset-remove-unused content/dam/projects

# Use current directory
aemcli asset-remove-unused .
```

#### How It Works
The command performs the following steps:

1. **Asset Discovery**: Recursively finds all `.content.xml` files with `jcr:primaryType="dam:Asset"` and common MIME types
2. **Reference Scanning**: Checks all `.content.xml` files in the jcr_root structure for references via:
   - `image="asset-path"` properties
   - `fileReference="asset-path"` properties  
   - `dam:folderThumbnailPaths="[asset-path,...]"` properties
3. **Smart Cleanup**: For assets only referenced in `folderThumbnailPaths`:
   - Removes the asset path from the thumbnail array
   - Marks asset for deletion
4. **Confirmation**: Shows detailed summary and asks for confirmation before deletion
5. **Deletion**: Removes entire parent folders containing unused asset `.content.xml` files

#### Options
- `--dry-run` - Preview what would be deleted without making any changes
- `--help` - Show detailed help and examples

#### Examples
```bash
# Preview unused assets in a project
aemcli asset-remove-unused content/dam/myproject --dry-run

# Clean up unused assets with confirmation
aemcli asset-remove-unused content/dam/myproject

# Check entire DAM folder
aemcli asset-remove-unused content/dam
```

### Repository Content Transfer Command

The `repo` command provides FTP-like functionality for transferring JCR content between the filesystem and AEM server.

#### Basic Usage
```bash
# Initial checkout from server
aemcli repo checkout /apps/myproject

# Upload changes to server
cd jcr_root/apps/myproject
aemcli repo put

# Download changes from server
aemcli repo get

# Check status
aemcli repo status
# or
aemcli repo st

# Show differences
aemcli repo diff
```

#### Advanced Usage
```bash
# Use custom server and credentials
aemcli repo status -s http://localhost:8080 -u user:password

# Force operations without confirmation
aemcli repo put -f

# Quiet mode (minimal output)
aemcli repo get -q

# Show server-side changes
aemcli repo serverdiff

# Show local changes
aemcli repo localdiff
```

#### Configuration Files

**`.repo` file** - Place in checkout or any parent directory:
```
server=http://server.com:8080
credentials=user:password
```

**`.repoignore` file** - Place in jcr_root directory to exclude files:
```
*.tmp
.cache/
*.log
```

#### Available Commands
- `checkout <jcr-path>` - Initial checkout of server content
- `put [path]` - Upload local content to server
- `get [path]` - Download server content to local
- `status [path]` - Show status of files (alias: `st`)
- `diff [path]` - Show local differences vs server
- `localdiff [path]` - Show local changes
- `serverdiff [path]` - Show server changes

#### Status Legend
- `M` - Modified
- `A` - Added locally / deleted remotely
- `D` - Deleted locally / added remotely
- `~ fd` - Conflict: local file vs. remote directory
- `~ df` - Conflict: local directory vs. remote file

### Examples

#### Example 1: Property Cleanup
```bash
# Clean all .content.xml files in an AEM project
aemcli content-cleanup property content/sites-franklin-commerce --dry-run

# Apply the changes
aemcli content-cleanup property content/sites-franklin-commerce

# Remove only specific custom properties
aemcli content-cleanup property /path/to/content cq:myCustomProp jcr:tempData

# Remove default properties plus custom ones
aemcli content-cleanup property /path/to/content --default cq:myCustomProp
```

#### Example 2: Node Cleanup
```bash
# Remove jcr:content nodes and folders from current directory
cd /path/to/aem/content
aemcli content-cleanup node jcr:content

# Preview what would be removed
aemcli content-cleanup node cq:dialog --dry-run

# Remove nodes from specific path
aemcli content-cleanup node rep:policy /path/to/content
```

#### Example 3: Repository Workflow
```bash
# Start from scratch with a server project
aemcli repo checkout /apps/myproject

# Make local changes
cd jcr_root/apps/myproject
vim .content.xml

# Check what changed
aemcli repo status

# Upload changes
aemcli repo put

# Later, download server changes
aemcli repo get

# Show differences
aemcli repo diff
```

#### Example 4: Asset Cleanup Workflow
```bash
# Preview unused assets before deletion
aemcli asset-remove-unused content/dam/myproject --dry-run

# Review the output, then proceed with cleanup
aemcli asset-remove-unused content/dam/myproject

# Clean up entire DAM folder
aemcli asset-remove-unused content/dam --dry-run
aemcli asset-remove-unused content/dam
```

## Development

### Project Structure
```
aem-cli/
├── src/aemcli/           # Main package
│   ├── cli.py           # CLI entry point
│   └── commands/        # Command modules
│       ├── content_cleanup.py
│       ├── asset_remove_unused.py
│       └── repo.py
├── tests/               # Test suite
│   ├── test_content_cleanup.py
│   ├── test_asset_remove_unused.py
│   ├── test_repo.py
│   └── test_content/    # Test data
├── requirements.txt     # Dependencies
├── pyproject.toml      # Project configuration
└── README.md           # This file
```

### Running Tests
```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=aemcli
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Local Development Checks
Run the same checks locally that GitHub Actions will run:

```bash
# Quick checks (syntax and tests)
./scripts/run_checks.sh

# Full checks (includes linting, formatting, type checking, security)
./scripts/run_checks.sh --full
```

### Pre-commit Hooks (Optional)
Set up pre-commit hooks to run checks automatically before each commit:

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks on all files (optional)
pre-commit run --all-files
```

## CI/CD

This project uses GitHub Actions for continuous integration and deployment. Two workflows are configured:

### Test Workflow (`test.yml`)
- **Triggers**: Every push and pull request
- **Purpose**: Quick feedback on test results and basic linting
- **Actions**:
  - Runs tests with pytest
  - Performs basic syntax and error checking with flake8
  - Uses Python 3.11 on Ubuntu

### CI Workflow (`ci.yml`)
- **Triggers**: Push/PR to main, master, or develop branches
- **Purpose**: Comprehensive testing and code quality checks
- **Actions**:
  - **Multi-version testing**: Tests against Python 3.8, 3.9, 3.10, 3.11, and 3.12
  - **Code quality**: Runs flake8, black, and mypy
  - **Test coverage**: Generates coverage reports and uploads to Codecov
  - **Security scanning**: Runs safety and bandit security checks
  - **Dependency caching**: Speeds up builds by caching pip dependencies

### Workflow Features
- **Parallel execution**: Test and security jobs run in parallel
- **Caching**: Pip dependencies are cached for faster builds
- **Coverage reporting**: Automatic upload to Codecov (optional)
- **Security checks**: Automated vulnerability scanning
- **Multi-Python support**: Ensures compatibility across Python versions

## Dependencies

### Core Dependencies
- **click>=8.0** - Command-line interface framework
- **requests>=2.28** - HTTP library for AEM API calls

### Development Dependencies
- **pytest>=7.0** - Testing framework
- **pytest-cov>=4.0** - Test coverage reporting
- **black>=23.0** - Code formatting
- **flake8>=6.0** - Code linting
- **mypy>=1.0** - Static type checking

### Optional Dependencies
- **colorama>=0.4.6** - Cross-platform colored terminal text
- **rich>=13.0** - Rich text and beautiful formatting

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`python -m pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Use type hints where appropriate

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions, issues, or contributions, please:
1. Check existing issues in the repository
2. Create a new issue with detailed information
3. Include steps to reproduce any bugs
4. Provide example files when relevant

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history and release notes.
