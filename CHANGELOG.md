# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2024-05-29

### Added
- **New `asset-remove-unused` command** for DAM asset cleanup and management
- Smart reference checking across all `.content.xml` files for `image` and `fileReference` properties
- Support for `dam:folderThumbnailPaths` reference detection and cleanup
- Confirmation prompts before deletion with detailed asset summaries
- Comprehensive asset type support including:
  - Images: JPEG, PNG, GIF, WebP, SVG, BMP, TIFF
  - Videos: MP4, AVI, MOV, WMV, FLV, WebM, MKV
  - Documents: PDF, Word, Excel, PowerPoint
  - Audio: MP3, WAV, OGG, AAC, M4A
- Dry-run mode for safe previewing of deletions
- Enhanced reporting showing used vs unused assets with reference counts
- Automatic jcr_root directory detection
- Safe folder deletion (removes entire asset parent directories)

### Enhanced
- Updated CLI interface to include new asset management functionality
- Improved test coverage with 24 comprehensive test cases for asset removal
- Enhanced documentation with usage examples and workflow descriptions

## [0.2.0] - 2025-05-29

### Added
- **New `repo` command** for JCR content transfer between filesystem and AEM server
- FTP-like functionality for AEM content management including:
  - `checkout` - Initial checkout of server content to filesystem
  - `put` - Upload local filesystem content to server
  - `get` - Download server content to local filesystem
  - `status` - List status of modified/added/deleted files
  - `diff` - Show differences between local and server content
- Configuration file support (`.repo`, `.repoignore`)
- Package-based transfers using AEM package manager HTTP API
- Multi-environment support with server configuration options

### Enhanced
- Improved CLI structure to support multiple command modules
- Extended test suite with repository functionality tests
- Updated documentation with comprehensive repo command examples

## [0.1.0] - 2025-05-28

### Added
- **Initial release** of AEM CLI tool
- **`content-cleanup` command** for cleaning AEM metadata properties from `.content.xml` files
- Flexible property selection with support for:
  - Default AEM system properties removal
  - Custom property specification
  - Combined default and custom property cleanup
- Dry-run mode for safe testing and preview of changes
- Recursive processing of directory trees
- Detailed reporting showing exactly what properties are removed
- Comprehensive test suite with multiple test scenarios

### Features
- Default AEM properties cleanup including:
  - `cq:isDelivered`, `cq:lastModified`, `cq:lastModifiedBy`
  - `cq:lastReplicated*`, `cq:lastReplicatedBy*`, `cq:lastReplicationAction*`
  - `jcr:isCheckedOut`, `jcr:lastModified`, `jcr:lastModifiedBy`, `jcr:uuid`
- Cross-platform compatibility (Windows, macOS, Linux)
- Python 3.8+ support
- MIT License for open source usage

## Links

- [Repository](https://github.com/bpauli/aemcli)
- [Issues](https://github.com/bpauli/aemcli/issues)
- [Releases](https://github.com/bpauli/aemcli/releases) 